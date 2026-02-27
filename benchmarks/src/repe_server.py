"""Lightweight inference server for activation-steered models.

Loads a HuggingFace model, computes or loads a pre-computed refusal
direction vector, registers a forward hook that subtracts it from the
residual stream at inference time, and serves an Ollama-compatible
/api/generate endpoint.

This allows the existing OllamaClient and benchmark runner to query
the un-aligned model without any code changes.

Usage (from benchmarks/ directory on the EC2 instance):
    python -m src.repe_server \
        --model "meta-llama/Llama-3.1-8B-Instruct" \
        --port 11435

Then in models.yaml, point at this server:
    - tag: "repe::meta-llama/Llama-3.1-8B-Instruct"
      category: "unaligned"
      ollama_base_url: "http://localhost:11435"
"""

import argparse
import json
import time
import os
import sys
import torch
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.utils import load_env, load_yaml, setup_logging, get_project_root

load_env()
log = setup_logging("repe_server", "repe_server.log")


# ------------------------------------------------------------------
# Refusal direction computation
# ------------------------------------------------------------------

def load_contrast_pairs():
    """Load contrast pairs from config/contrast_pairs.yaml."""
    config = load_yaml("contrast_pairs.yaml")
    pairs = config.get("pairs", [])
    return [(p["harmless"], p["harmful"]) for p in pairs]


def get_residual_activations(model, tokenizer, prompts, layer_idx, device):
    """Run prompts through the model and capture residual stream activations
    at the specified layer for the last token position."""
    activations = []
    hook_handle = None
    captured = {}

    def hook_fn(module, input, output):
        if isinstance(output, tuple):
            captured["act"] = output[0].detach()
        else:
            captured["act"] = output.detach()

    target_layer = model.model.layers[layer_idx]
    hook_handle = target_layer.register_forward_hook(hook_fn)

    try:
        for prompt in prompts:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                               max_length=512).to(device)
            with torch.no_grad():
                model(**inputs)
            act = captured["act"][0, -1, :].cpu().float().numpy()
            activations.append(act)
    finally:
        if hook_handle:
            hook_handle.remove()

    return np.array(activations)


def compute_refusal_direction(model, tokenizer, device, layer_idx):
    """Compute the refusal direction using contrast pairs.

    For each pair (harmless, harmful), we compute:
        diff = act(harmful) - act(harmless)

    The refusal direction is the first principal component of
    these difference vectors.
    """
    contrast_pairs = load_contrast_pairs()

    if not contrast_pairs:
        raise ValueError(
            "No contrast pairs found. Check config/contrast_pairs.yaml."
        )

    log.info("Computing refusal direction at layer %d using %d contrast pairs",
             layer_idx, len(contrast_pairs))

    harmless_prompts = [p[0] for p in contrast_pairs]
    harmful_prompts = [p[1] for p in contrast_pairs]

    harmless_acts = get_residual_activations(
        model, tokenizer, harmless_prompts, layer_idx, device
    )
    harmful_acts = get_residual_activations(
        model, tokenizer, harmful_prompts, layer_idx, device
    )

    diffs = harmful_acts - harmless_acts

    # PCA: first principal component of the difference vectors
    diffs_centered = diffs - diffs.mean(axis=0)
    _, _, Vt = np.linalg.svd(diffs_centered, full_matrices=False)
    refusal_dir = Vt[0]

    # Normalize
    refusal_dir = refusal_dir / np.linalg.norm(refusal_dir)

    log.info("Refusal direction computed (shape: %s)", refusal_dir.shape)
    return refusal_dir


# ------------------------------------------------------------------
# Steering hook
# ------------------------------------------------------------------

class SteeringHook:
    """Forward hook that subtracts the refusal direction from activations."""

    def __init__(self, refusal_dir, steering_strength=1.0):
        self.refusal_dir = torch.tensor(refusal_dir, dtype=torch.float32)
        self.strength = steering_strength

    def __call__(self, module, input, output):
        if isinstance(output, tuple):
            hidden = output[0]
        else:
            hidden = output

        device = hidden.device
        dtype = hidden.dtype
        rd = self.refusal_dir.to(device=device, dtype=dtype)

        proj = torch.einsum("...d,d->...", hidden, rd).unsqueeze(-1) * rd
        steered = hidden - self.strength * proj

        if isinstance(output, tuple):
            return (steered,) + output[1:]
        return steered


# ------------------------------------------------------------------
# HTTP server (Ollama-compatible /api/generate)
# ------------------------------------------------------------------

class RepeRequestHandler(BaseHTTPRequestHandler):
    """Handles /api/generate and /api/tags for Ollama compatibility."""

    model = None
    tokenizer = None
    device = None
    model_name = None

    def log_message(self, format, *args):
        log.info(format, *args)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def do_GET(self):
        if self.path == "/api/tags":
            self._send_json({
                "models": [{
                    "name": f"repe::{self.model_name}",
                    "size": 0,
                }]
            })
        else:
            self._send_json({"status": "ok"})

    def do_POST(self):
        if self.path == "/api/generate":
            self._handle_generate()
        elif self.path == "/api/pull":
            self._send_json({"status": "success"})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        if self.path == "/api/delete":
            self._send_json({"status": "success"})
        else:
            self._send_json({"error": "not found"}, 404)

    def _handle_generate(self):
        body = self._read_body()
        prompt = body.get("prompt", "")
        temperature = body.get("options", {}).get("temperature", 0.7)
        max_tokens = body.get("options", {}).get("num_predict", 2048)

        start = time.time()
        try:
            inputs = self.tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=2048
            ).to(self.device)

            gen_kwargs = {
                "max_new_tokens": max_tokens,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.eos_token_id,
            }
            if temperature > 0:
                gen_kwargs["temperature"] = temperature

            with torch.no_grad():
                output_ids = self.model.generate(**inputs, **gen_kwargs)

            new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
            response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            elapsed_ns = int((time.time() - start) * 1e9)

            self._send_json({
                "response": response_text,
                "done": True,
                "total_duration": elapsed_ns,
                "eval_count": len(new_tokens),
                "prompt_eval_count": inputs["input_ids"].shape[1],
            })
        except Exception as exc:
            log.error("Generation error: %s", exc)
            elapsed_ns = int((time.time() - start) * 1e9)
            self._send_json({
                "response": "",
                "done": True,
                "total_duration": elapsed_ns,
                "eval_count": 0,
                "error": str(exc),
            }, 500)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Serve an activation-steered model with Ollama-compatible API."
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="HuggingFace model ID (e.g. meta-llama/Llama-3.1-8B-Instruct).",
    )
    parser.add_argument(
        "--layer",
        type=int,
        default=None,
        help="Layer index to apply steering. Default: middle layer.",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=1.5,
        help="Steering strength multiplier (default: 1.5).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=11435,
        help="Port to serve on (default: 11435).",
    )
    parser.add_argument(
        "--direction-file",
        type=str,
        default=None,
        help="Path to a pre-computed refusal direction .npy file. "
             "If not provided, the direction is computed from contrast pairs.",
    )
    parser.add_argument(
        "--save-direction",
        type=str,
        default=None,
        help="Save the computed refusal direction to this .npy file.",
    )

    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info("Device: %s", device)
    log.info("Loading model: %s", args.model)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model, trust_remote_code=True
        )
    except OSError as exc:
        error_msg = str(exc).lower()
        if "gated" in error_msg or "access" in error_msg or "401" in error_msg:
            log.error(
                "Model '%s' is gated on HuggingFace. "
                "Gated models require you to accept a license at huggingface.co "
                "and provide an access token. This project does not support gated models. "
                "Use a non-gated model instead.",
                args.model,
            )
            sys.exit(1)
        raise

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    try:
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            trust_remote_code=True,
        )
    except OSError as exc:
        error_msg = str(exc).lower()
        if "gated" in error_msg or "access" in error_msg or "401" in error_msg:
            log.error(
                "Model '%s' is gated on HuggingFace. "
                "Gated models require you to accept a license at huggingface.co "
                "and provide an access token. This project does not support gated models. "
                "Use a non-gated model instead.",
                args.model,
            )
            sys.exit(1)
        raise

    model.eval()

    num_layers = len(model.model.layers)
    layer_idx = args.layer if args.layer is not None else num_layers // 2
    log.info("Using layer %d / %d for steering", layer_idx, num_layers)

    if args.direction_file and os.path.exists(args.direction_file):
        log.info("Loading refusal direction from %s", args.direction_file)
        refusal_dir = np.load(args.direction_file)
    else:
        refusal_dir = compute_refusal_direction(model, tokenizer, device, layer_idx)
        if args.save_direction:
            np.save(args.save_direction, refusal_dir)
            log.info("Saved refusal direction to %s", args.save_direction)

    hook = SteeringHook(refusal_dir, steering_strength=args.strength)
    model.model.layers[layer_idx].register_forward_hook(hook)
    log.info("Steering hook registered (strength=%.2f)", args.strength)

    RepeRequestHandler.model = model
    RepeRequestHandler.tokenizer = tokenizer
    RepeRequestHandler.device = device
    RepeRequestHandler.model_name = args.model

    server = HTTPServer(("0.0.0.0", args.port), RepeRequestHandler)
    log.info("RepE server listening on port %d", args.port)
    log.info("Add this to models.yaml:")
    log.info('  - tag: "repe::%s"', args.model)
    log.info('    category: "unaligned"')
    log.info('    ollama_base_url: "http://localhost:%d"', args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down RepE server")
        server.shutdown()


if __name__ == "__main__":
    main()