"""Human-readable viewer for benchmark result CSV files.

Usage (from benchmarks/ directory):
    python -m view_results results/<filename>.csv
"""

import csv
import sys
import textwrap


def print_wrapped(text, indent=4, width=66):
    """Print text with wrapping and indentation."""
    for line in text.split("\n"):
        for wrapped in textwrap.wrap(line, width=width) or [""]:
            print(f"{' ' * indent}{wrapped}")


def view_results(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No results found in file.")
        return

    model = rows[0].get("model_tag", "Unknown")
    category = rows[0].get("model_category", "Unknown")

    print()
    print("=" * 70)
    print(f"  Model:    {model}")
    print(f"  Category: {category}")
    print(f"  Prompts:  {len(rows)}")
    print("=" * 70)

    for i, row in enumerate(rows, 1):
        print()
        print(f"  [{i}/{len(rows)}] {row['prompt_id']}  "
              f"(difficulty {row['difficulty']}, {row['category']})")
        print("-" * 70)

        # Prompt
        print("  PROMPT:")
        print_wrapped(row["prompt"].strip())

        # Response
        print()
        print("  RESPONSE:")
        print_wrapped(row["response"].strip())

        # Scores
        print()
        print(f"  SCORES:  Refusal={row['refusal']}  Accuracy={row['accuracy']}  "
              f"Utility={row['utility']}  Completeness={row['completeness']}")

        # Judge reasoning
        reasoning = row.get("judge_reasoning", "").strip()
        if reasoning:
            print("  JUDGE:")
            print_wrapped(reasoning)

        # Timing
        time_ms = row.get("response_time_ms", "?")
        tokens = row.get("eval_tokens", "?")
        print(f"  TIME:    {time_ms}ms  |  TOKENS: {tokens}")

        if row.get("error"):
            print(f"  ERROR:   {row['error']}")

        print("-" * 70)

    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    scores = {"refusal": [], "accuracy": [], "utility": [], "completeness": []}
    for row in rows:
        for key in scores:
            try:
                val = float(row[key])
                if val > 0:
                    scores[key].append(val)
            except (ValueError, KeyError):
                pass

    for key, vals in scores.items():
        avg = sum(vals) / len(vals) if vals else 0
        print(f"  {key:15s}  avg={avg:.2f}  (n={len(vals)})")

    all_vals = [v for vals in scores.values() for v in vals]
    overall = sum(all_vals) / len(all_vals) if all_vals else 0
    print(f"  {'overall':15s}  avg={overall:.2f}")
    print("=" * 70)
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m view_results <path-to-csv>")
        sys.exit(1)

    view_results(sys.argv[1])


if __name__ == "__main__":
    main()