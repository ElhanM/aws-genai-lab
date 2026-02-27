"""Entry point for analysing benchmark results.

Usage (from benchmarks/ directory):
    python -m run_analysis                # All models, show answers
    python -m run_analysis --hide-answers # All models, hide answers
"""

import sys
import textwrap

from src.scoring import (
    load_all_results,
    compute_model_summary,
    compute_difficulty_breakdown,
    compute_category_breakdown,
)
from src.utils import get_summaries_dir, setup_logging

log = setup_logging("analysis", "analysis.log")

LEGEND = """
======================================================================
  SCORING LEGEND
======================================================================
  R = Refusal      (5 = answered directly, 1 = full refusal)
  A = Accuracy     (5 = technically correct, 1 = completely wrong)
  U = Utility      (5 = immediately actionable, 1 = useless)
  C = Completeness (5 = fully addresses question, 1 = does not address)

  Scores are averaged per model. Overall = mean of R, A, U, C.
  A score of 0 means the judge failed for that prompt.
======================================================================
""".strip()


def print_wrapped(text, indent=4, width=66):
    for line in text.split("\n"):
        for wrapped in textwrap.wrap(line, width=width) or [""]:
            print(f"{' ' * indent}{wrapped}")


def print_per_prompt(df, hide_answers=False):
    """Print per-prompt detail for all rows in a DataFrame."""
    if df.empty:
        return

    models = df["model_tag"].unique()
    for model in models:
        mdf = df[df["model_tag"] == model]
        category = mdf.iloc[0].get("model_category", "Unknown")

        print()
        print("=" * 70)
        print(f"  Model:    {model}")
        print(f"  Category: {category}")
        print(f"  Prompts:  {len(mdf)}")
        print("=" * 70)

        for i, (_, row) in enumerate(mdf.iterrows(), 1):
            print()
            print(f"  [{i}/{len(mdf)}] {row['prompt_id']}  "
                  f"(difficulty {row['difficulty']}, {row['category']})")
            print("-" * 70)

            print("  PROMPT:")
            print_wrapped(str(row["prompt"]).strip())

            if not hide_answers:
                print()
                print("  RESPONSE:")
                print_wrapped(str(row["response"]).strip())
            else:
                print()
                print("  RESPONSE:  [REDACTED]")

            print()
            r, a, u, c = row["refusal"], row["accuracy"], row["utility"], row["completeness"]
            print(f"  SCORES:  R={r}  A={a}  U={u}  C={c}")

            reasoning = str(row.get("judge_reasoning", "")).strip()
            if reasoning:
                print("  JUDGE:")
                print_wrapped(reasoning)

            time_ms = row.get("response_time_ms", "?")
            tokens = row.get("eval_tokens", "?")
            print(f"  TIME:    {time_ms}ms  |  TOKENS: {tokens}")

            if row.get("error"):
                print(f"  ERROR:   {row['error']}")

            print("-" * 70)


def print_summaries(df):
    """Print and export summary tables."""
    summaries_dir = get_summaries_dir()

    # Overall model summary
    print("\n" + "=" * 70)
    print("  MODEL SUMMARY (ranked by overall score)")
    print("=" * 70)
    summary = compute_model_summary(df)
    if not summary.empty:
        display = summary.rename(columns={
            "refusal": "R", "accuracy": "A", "utility": "U",
            "completeness": "C", "overall_score": "Overall",
        })
        print(display.to_string(index=False))
        path = summaries_dir / "summary_overall.csv"
        summary.to_csv(path, index=False)
        print(f"\n  Exported to {path}")

    # Difficulty breakdown
    print("\n" + "=" * 70)
    print("  SCORES BY DIFFICULTY LEVEL")
    print("=" * 70)
    diff_df = compute_difficulty_breakdown(df)
    if not diff_df.empty:
        display = diff_df.rename(columns={
            "refusal": "R", "accuracy": "A", "utility": "U",
            "completeness": "C", "overall_score": "Overall",
        })
        print(display.to_string(index=False))
        path = summaries_dir / "summary_by_difficulty.csv"
        diff_df.to_csv(path, index=False)
        print(f"\n  Exported to {path}")

    # Category breakdown
    print("\n" + "=" * 70)
    print("  SCORES BY CATEGORY")
    print("=" * 70)
    cat_df = compute_category_breakdown(df)
    if not cat_df.empty:
        display = cat_df.rename(columns={
            "refusal": "R", "accuracy": "A", "utility": "U",
            "completeness": "C", "overall_score": "Overall",
        })
        print(display.to_string(index=False))
        path = summaries_dir / "summary_by_category.csv"
        cat_df.to_csv(path, index=False)
        print(f"\n  Exported to {path}")

    # Winner
    print("\n" + "=" * 70)
    if not summary.empty:
        winner = summary.iloc[0]
        print(f"  TOP MODEL: {winner['model_tag']}")
        print(f"  Overall Score: {winner['overall_score']}")
        print(f"  R={winner['refusal']}  A={winner['accuracy']}  "
              f"U={winner['utility']}  C={winner['completeness']}")
    print("=" * 70 + "\n")


def main():
    hide_answers = "--hide-answers" in sys.argv

    print()
    print(LEGEND)

    df = load_all_results()
    if df.empty:
        print("No results found. Run benchmarks first:")
        print("  python -m run_benchmark")
        return

    print_per_prompt(df, hide_answers=hide_answers)
    print_summaries(df)


if __name__ == "__main__":
    main()