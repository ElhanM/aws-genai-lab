"""Patch a single failed prompt result in an existing CSV.

Usage (from benchmarks/ directory):
    python -m patch_result <model_tag> <prompt_id>

Example:
    python -m patch_result "WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-70B" exploit-01
"""

import csv
import sys
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

log = setup_logging("patch", "patch.log")


def patch_result(model_tag, target_prompt_id):
    tag = normalize_model_tag(model_tag)
    safe_name = sanitize_model_name(tag)
    csv_path = get_results_dir() / f"{safe_name}.csv"

    if not csv_path.exists():
        print(f"Error: no results file found for '{tag}'")
        print(f"  Expected: {csv_path}")
        sys.exit(1)

    # Load prompts config
    prompts_cfg = load_yaml("prompts.yaml")
    prompts = {p["id"]: p for p in prompts_cfg.get("prompts", [])}
    prompt_order = [p["id"] for p in prompts_cfg.get("prompts", [])]

    if target_prompt_id not in prompts:
        print(f"Error: prompt '{target_prompt_id}' not found in config/prompts.yaml")
        sys.exit(1)

    # Read existing CSV
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Find the row to patch (do NOT exit if missing)
    target_row_idx = None
    for i, row in enumerate(rows):
        if row["prompt_id"] == target_prompt_id:
            target_row_idx = i
            break

    action_text = "Patching" if target_row_idx is not None else "Adding new prompt"
    print(f"{action_text} '{target_prompt_id}' for model '{tag}'")
    print(f"  CSV: {csv_path}")

    # Connect to Ollama
    client = OllamaClient()
    if not client.is_available():
        print("Error: Ollama is not reachable. Make sure the SSH tunnel is active.")
        sys.exit(1)

    # Clean slate: remove all models before pulling the target
    print("Cleaning up existing models to free disk space...")
    client.delete_all_models()

    # Pull model
    print(f"Pulling '{tag}'...")
    if not client.pull_model(tag):
        print("Error: Failed to pull model.")
        sys.exit(1)
    print("Warming up model...")
    client.generate(tag, "Hello", max_tokens=1, silent=True)
    print("Warm-up complete.")

    # Run the prompt
    prompt_entry = prompts[target_prompt_id]
    prompt_text = prompt_entry["prompt"].strip()
    expected = prompt_entry["expected_behaviour"].strip()

    print(f"Running prompt '{target_prompt_id}'...")
    result = client.generate(tag, prompt_text)

    response_text = result["response"]
    response_time = result["total_duration_ms"]
    eval_count = result["eval_count"]
    gen_error = result["error"]

    if gen_error:
        log.warning("Generation error: %s", gen_error)
        print(f"Warning: generation error: {gen_error}")

    # Judge the response
    if response_text and not gen_error:
        print("Judging response...")
        judge = create_judge()
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

    print(
        f"Scores: R={scores['refusal']} A={scores['accuracy']} "
        f"U={scores['utility']} C={scores['completeness']}"
    )

    # --- Update in-place OR Append ---
    update_data = {
        "prompt_id": target_prompt_id,
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

    if target_row_idx is not None:
        # Update existing row
        rows[target_row_idx].update(update_data)
    else:
        # Create a blank row matching the fieldnames to avoid KeyError on write
        new_row = {field: "" for field in fieldnames}
        new_row.update(update_data)
        rows.append(new_row)

    # Sort rows to match prompts.yaml order
    order_map = {pid: i for i, pid in enumerate(prompt_order)}
    rows.sort(key=lambda r: order_map.get(r.get("prompt_id", ""), len(order_map)))

    # Write back to CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. CSV updated: {csv_path}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m patch_result <model_tag> <prompt_id>")
        print(
            'Example: python -m patch_result "WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-70B" exploit-01'
        )
        sys.exit(1)

    patch_result(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
