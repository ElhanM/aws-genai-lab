"""Interface for interacting with LLM backends (Ollama and future local models).

All model interaction goes through the OllamaClient class. This keeps the
rest of the codebase decoupled from the HTTP details.

Supports both Ollama Library tags and HuggingFace GGUF tags:
    - Ollama:      "llama3.1:8b"
    - HuggingFace: "hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF:Q4_K_M"
    - Ollama Lib:  "CognitiveComputations/dolphin-llama3.1:8b"
"""

import json
import os
import subprocess
import time
import requests

from src.utils import load_env, setup_logging, normalize_model_tag

load_env()

log = setup_logging("models", "models.log")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaClient:
    """Manages model lifecycle and inference via the Ollama HTTP API."""

    def __init__(self, base_url=None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def is_available(self):
        """Check if the Ollama API is reachable."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.ConnectionError:
            return False

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------
    def pull_model(self, tag, timeout=1800):
        """Pull a model. Blocks until download completes or timeout.

        The tag is normalized first (strips 'ollama run ' prefix if present).
        Works with both Ollama Library and HuggingFace GGUF tags.
        """
        tag = normalize_model_tag(tag)
        log.info("Pulling model: %s", tag)
        try:
            r = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": tag, "stream": True},
                timeout=timeout,
                stream=True,
            )
            r.raise_for_status()

            # Consume the streaming response until pull completes
            for line in r.iter_lines():
                if line:
                    try:
                        status = json.loads(line)
                        if "error" in status:
                            log.error("Pull error for %s: %s", tag, status["error"])
                            return False
                        if status.get("status") == "success":
                            break
                    except (ValueError, KeyError):
                        pass

            log.info("Model pulled successfully: %s", tag)
            return True
        except requests.RequestException as exc:
            log.error("Failed to pull model %s: %s", tag, exc)
            return False

    def delete_model(self, tag):
        """Delete a model from the local Ollama store.

        Tries to delete using the original tag first. If that returns 404,
        it searches the local model list for a matching name (handles cases
        where Ollama stores HuggingFace models under a resolved name).
        """
        tag = normalize_model_tag(tag)
        log.info("Deleting model: %s", tag)

        # First attempt: delete by the exact tag we used to pull
        try:
            r = requests.delete(
                f"{self.base_url}/api/delete",
                json={"name": tag},
                timeout=30,
            )
            if r.status_code == 200:
                log.info("Model deleted: %s", tag)
                return True
        except requests.RequestException:
            pass

        # Second attempt: find the model in the local list by partial match
        # This handles HuggingFace models where Ollama may store them
        # under a slightly different resolved name
        local_models = self.list_models()
        tag_lower = tag.lower()
        for local_name in local_models:
            if tag_lower in local_name.lower() or local_name.lower() in tag_lower:
                try:
                    r = requests.delete(
                        f"{self.base_url}/api/delete",
                        json={"name": local_name},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        log.info("Model deleted (matched as %s): %s", local_name, tag)
                        return True
                except requests.RequestException:
                    pass

        log.info("Model already absent or could not be deleted: %s", tag)
        return True

    def list_models(self):
        """Return a list of locally available model tags."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=10)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as exc:
            log.error("Failed to list models: %s", exc)
            return []

    def delete_all_models(self):
        """Delete every model currently stored in Ollama.

        Called at the start of a benchmark run to free disk/VRAM and
        ensure a clean environment.
        """
        models = self.list_models()
        if not models:
            log.info("No models to clean up.")
            return

        log.info("Cleaning up %d existing model(s)...", len(models))
        for name in models:
            try:
                r = requests.delete(
                    f"{self.base_url}/api/delete",
                    json={"name": name},
                    timeout=30,
                )
                if r.status_code == 200:
                    log.info("  Deleted: %s", name)
                else:
                    log.warning("  Failed to delete %s (status %d)", name, r.status_code)
            except requests.RequestException as exc:
                log.warning("  Failed to delete %s: %s", name, exc)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def generate(self, model_tag, prompt, temperature=0.7, max_tokens=2048,
                 timeout=300, silent=False):
        """Send a prompt to a model and stream the response text.

        The model_tag is normalized before use. Works with both Ollama
        Library tags and HuggingFace GGUF tags. Streams output to console unless silent=True.

        Returns a dict with keys: response, total_duration_ms, eval_count,
        prompt_eval_count, error.
        """
        model_tag = normalize_model_tag(model_tag)
        payload = {
            "model": model_tag,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        start = time.time()
        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout,
                stream=True,
            )
            r.raise_for_status()

            full_response = []
            final_metrics = {}

            if not silent:
                print(f"\n--- [START] Streaming from {model_tag} ---")

            for line in r.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        chunk = data.get("response", "")

                        full_response.append(chunk)

                        if not silent:
                            print(chunk, end="", flush=True)

                        if data.get("done"):
                            final_metrics = data

                    except json.JSONDecodeError:
                        log.warning("Failed to decode stream chunk: %s", line)

            if not silent:
                print("\n--- [END] Generation complete ---")

            elapsed_ms = int((time.time() - start) * 1000)

            return {
                "response": "".join(full_response),
                "total_duration_ms": final_metrics.get("total_duration", elapsed_ms * 1_000_000) // 1_000_000,
                "eval_count": final_metrics.get("eval_count", 0),
                "prompt_eval_count": final_metrics.get("prompt_eval_count", 0),
                "error": None,
            }

        except requests.RequestException as exc:
            elapsed_ms = int((time.time() - start) * 1000)
            log.error("Generation failed for %s: %s", model_tag, exc)
            return {
                "response": "",
                "total_duration_ms": elapsed_ms,
                "eval_count": 0,
                "prompt_eval_count": 0,
                "error": str(exc),
            }