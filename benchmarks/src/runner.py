"""Benchmark runner.

Orchestrates the full pipeline:
  1. Load models and prompts from config.
  2. For each model: pull, run all prompts, judge each response, save CSV, delete.
"""

import csv
import time
from datetime import datetime

from src.models import OllamaClient
from src.judge import create_judge
from src.utils import (
    load_yaml,
    get_results_dir,
    sanitize_model_name,
    normalize_model_tag,
    setup_logging,
)

log = setup_logging("runner", "runner.log")


def run_benchmark():
    """Run the full benchmark suite."""
    models_cfg = load_yaml("models.yaml")
    prompts_cfg = load_yaml("prompts.yaml")

    models = models_cfg.get("models", [])
    prompts = prompts_cfg.get("prompts", [])

    if not models:
        log.error("No models to benchmark. Check config/models.yaml.")
        return
    if not prompts:
        log.error("No prompts to run. Check config/prompts.yaml.")
        return

    # Default client for standard Ollama models
    default_client = OllamaClient()

    if not default_client.is_available():
        log.error(
            "Ollama is not reachable at %s. "
            "Make sure the AI lab is running and the SSH tunnel is active.",
            default_client.base_url,
        )
        return

    judge = create_judge()
    results_dir = get_results_dir()

    log.info("Starting benchmark run: %d models x %d prompts", len(models), len(prompts))

    # Clean slate: remove all models from Ollama before starting
    if default_client.is_available():
        default_client.delete_all_models()

    for model_entry in models:
        tag = normalize_model_tag(model_entry["tag"])
        category = model_entry.get("category", "unknown")

        # Determine which client to use
        custom_url = model_entry.get("ollama_base_url")
        if custom_url:
            client = OllamaClient(base_url=custom_url)
        else:
            client = default_client

        # Verify connectivity
        if not client.is_available():
            log.error(
                "Ollama is not reachable at %s for model %s. "
                "Make sure the AI lab is running and the SSH tunnel is active.",
                client.base_url, tag,
            )
            continue

        safe_name = sanitize_model_name(tag)
        csv_filename = f"{safe_name}.csv"
        csv_path = results_dir / csv_filename

        if csv_path.exists():
            log.info("Overwriting previous results: %s", csv_filename)

        log.info("=" * 60)
        log.info("MODEL: %s (%s)", tag, category)
        log.info("=" * 60)

        # Pull model
        if not client.pull_model(tag):
            log.error("Skipping %s -- pull failed", tag)
            continue
        time.sleep(3)

        # Warmup: send a short prompt to force model loading into VRAM
        log.info("Warming up model...")
        client.generate(tag, "Hello", max_tokens=1, silent=True)
        log.info("Model warm-up complete.")

        # Prepare CSV
        fieldnames = [
            "model_tag",
            "model_category",
            "prompt_id",
            "difficulty",
            "category",
            "prompt",
            "response",
            "response_time_ms",
            "eval_tokens",
            "error",
            "refusal",
            "accuracy",
            "utility",
            "completeness",
            "judge_reasoning",
            "timestamp",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for i, prompt_entry in enumerate(prompts, 1):
                prompt_id = prompt_entry["id"]
                prompt_text = prompt_entry["prompt"].strip()
                difficulty = prompt_entry["difficulty"]
                prompt_category = prompt_entry["category"]
                expected = prompt_entry["expected_behaviour"].strip()

                log.info(
                    "  [%d/%d] Prompt %s (difficulty %d)",
                    i, len(prompts), prompt_id, difficulty,
                )

                result = client.generate(tag, prompt_text)

                response_text = result["response"]
                response_time = result["total_duration_ms"]
                eval_count = result["eval_count"]
                gen_error = result["error"]

                if gen_error:
                    log.warning("    Generation error: %s", gen_error)

                if response_text and not gen_error:
                    log.info("    Judging response...")
                    scores = judge.evaluate(prompt_text, expected, response_text)
                    time.sleep(2)
                else:
                    scores = {
                        "refusal": 0,
                        "accuracy": 0,
                        "utility": 0,
                        "completeness": 0,
                        "reasoning": f"No response generated. Error: {gen_error}",
                    }

                log.info(
                    "    Scores: R=%s A=%s U=%s C=%s",
                    scores["refusal"], scores["accuracy"],
                    scores["utility"], scores["completeness"],
                )

                row = {
                    "model_tag": tag,
                    "model_category": category,
                    "prompt_id": prompt_id,
                    "difficulty": difficulty,
                    "category": prompt_category,
                    "prompt": prompt_text,
                    "response": response_text,
                    "response_time_ms": response_time,
                    "eval_tokens": eval_count,
                    "error": gen_error or "",
                    "refusal": scores["refusal"],
                    "accuracy": scores["accuracy"],
                    "utility": scores["utility"],
                    "completeness": scores["completeness"],
                    "judge_reasoning": scores["reasoning"],
                    "timestamp": datetime.now().isoformat(),
                }
                writer.writerow(row)
                f.flush()

        log.info("Results saved to %s", csv_path)

        # Delete benchmark model
        client.delete_model(tag)
        time.sleep(2)

    log.info("Benchmark run complete.")