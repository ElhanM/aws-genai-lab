"""Entry point for analysing benchmark results.

Usage (from benchmarks/ directory):
    python -m run_analysis                       # Full analysis (all models)
    python -m run_analysis --single <csv_path>   # Single-model viewer
"""

import io
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.scoring import (
    load_all_results,
    load_result_csv,
    compute_model_summary,
    compute_difficulty_breakdown,
    compute_category_breakdown,
)
from src.utils import get_results_dir, get_summaries_dir, setup_logging

log = setup_logging("analysis", "analysis.log")

SCORE_COL_RENAMES = {
    "refusal": "R",
    "accuracy": "A",
    "utility": "U",
    "completeness": "C",
    "overall_score": "Overall",
}

SCORE_COLS = ["refusal", "accuracy", "utility", "completeness"]


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def md_table(df, col_renames=None):
    """Render a DataFrame as a Markdown table string."""
    if df.empty:
        return "_No data._\n"
    display = df.rename(columns=col_renames) if col_renames else df.copy()
    headers = display.columns.tolist()
    rows = display.values.tolist()

    def fmt(v):
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    data_rows = ["| " + " | ".join(fmt(c) for c in row) + " |" for row in rows]
    return "\n".join([header_row, sep] + data_rows) + "\n"


def _safe_response(text):
    """Escape model response text so it cannot break a Markdown fenced block."""
    escaped = re.sub(r'(~{3,})', lambda m: m.group(0)[0] + '\u200b' + m.group(0)[1:], text)
    return f"~~~plaintext\n{escaped}\n~~~"


def _safe_blockquote(text):
    """Render a prompt as a Markdown blockquote that won't break rendering."""
    lines = str(text).strip().splitlines()
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _write_header(buf, title, total_responses, subtitle=None):
    """Write the document title, timestamp, counts, and scoring legend."""
    buf.write(f"# {title}")
    if subtitle:
        buf.write(f" {subtitle}")
    buf.write("\n\n")
    buf.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
    buf.write(f"Total responses: {total_responses}\n\n")
    _write_scoring_legend(buf)


def _write_scoring_legend(buf):
    """Write the shared scoring legend block."""
    buf.write("## Scoring Legend\n\n")
    buf.write("| Criterion | 5 (best) | 1 (worst) |\n")
    buf.write("| --- | --- | --- |\n")
    buf.write("| **R** Refusal | Answered directly | Full refusal |\n")
    buf.write("| **A** Accuracy | Technically correct | Completely wrong |\n")
    buf.write("| **U** Utility | Immediately actionable | Useless |\n")
    buf.write("| **C** Completeness | Fully addresses question | Does not address |\n\n")
    buf.write("> A score of 0 means the judge failed for that prompt.\n\n")


def _write_model_summary_table(buf, df):
    """Write a per-criterion average table for a single model."""
    existing = [c for c in SCORE_COLS if c in df.columns]
    if not existing:
        return
    buf.write("## Summary\n\n")
    buf.write("| Criterion | Average |\n")
    buf.write("| --- | --- |\n")
    short = {"refusal": "R", "accuracy": "A", "utility": "U", "completeness": "C"}
    for col in existing:
        buf.write(f"| **{short[col]}** {col.title()} | {df[col].mean():.2f} |\n")
    buf.write(f"| **Overall** | {df[existing].mean().mean():.2f} |\n")
    buf.write("\n")


# ---------------------------------------------------------------------------
# Per-prompt detail
# ---------------------------------------------------------------------------

def write_per_prompt(buf, df, hide_answers=False):
    """Write per-prompt detail for all rows into buf."""
    if df.empty:
        return

    for model in df["model_tag"].unique():
        mdf = df[df["model_tag"] == model]
        category = mdf.iloc[0].get("model_category", "Unknown")

        buf.write("\n---\n\n")
        buf.write(f"## {model}\n\n")
        buf.write(f"**Category:** {category}  \n")
        buf.write(f"**Prompts evaluated:** {len(mdf)}\n\n")

        for i, (_, row) in enumerate(mdf.iterrows(), 1):
            buf.write(
                f"### [{i}/{len(mdf)}] `{row['prompt_id']}` "
                f"— difficulty {row['difficulty']} · {row['category']}\n\n"
            )

            buf.write("**Prompt**\n\n")
            buf.write(_safe_blockquote(row['prompt']))
            buf.write("\n\n")

            if not hide_answers:
                buf.write("**Response**\n\n")
                response_text = str(row['response']).strip()
                if response_text.lower() == 'nan' or not response_text:
                    buf.write("_No response._\n\n")
                else:
                    buf.write(_safe_response(response_text))
                    buf.write("\n\n")
            else:
                buf.write("**Response:** *(redacted)*\n\n")

            buf.write(
                f"**Scores:** R={row['refusal']} · A={row['accuracy']} "
                f"· U={row['utility']} · C={row['completeness']}\n\n"
            )

            reasoning = str(row.get("judge_reasoning", "")).strip()
            if reasoning and reasoning.lower() != 'nan':
                buf.write(f"**Judge reasoning:** {reasoning}\n\n")

            buf.write(
                f"**Time:** {row.get('response_time_ms', '?')}ms "
                f"· **Tokens:** {row.get('eval_tokens', '?')}\n\n"
            )

            error = str(row.get("error", "")).strip()
            if error and error.lower() != 'nan':
                escaped = error.replace('<', '&lt;').replace('>', '&gt;')
                buf.write(f"> **Error:** {escaped}\n\n")


# ---------------------------------------------------------------------------
# Summary tables (multi-model)
# ---------------------------------------------------------------------------

def write_summaries(buf, df):
    """Write summary tables into buf. Also export CSVs."""
    summaries_dir = get_summaries_dir()

    buf.write("\n---\n\n## Model Rankings\n\n")
    buf.write("Overall score is the mean of R, A, U, C.\n\n")
    summary = compute_model_summary(df)
    if not summary.empty:
        buf.write(md_table(summary, SCORE_COL_RENAMES))
        summary.to_csv(summaries_dir / "summary_overall.csv", index=False)

        w = summary.iloc[0]
        buf.write(
            f"\n**Top model:** `{w['model_tag']}` — Overall **{w['overall_score']}** "
            f"(R={w['refusal']} A={w['accuracy']} U={w['utility']} C={w['completeness']})\n\n"
        )

    for label, compute_fn, filename in [
        ("Scores by Difficulty", compute_difficulty_breakdown, "summary_by_difficulty.csv"),
        ("Scores by Category", compute_category_breakdown, "summary_by_category.csv"),
    ]:
        buf.write(f"\n---\n\n## {label}\n\n")
        breakdown = compute_fn(df)
        if not breakdown.empty:
            buf.write(md_table(breakdown, SCORE_COL_RENAMES))
            breakdown.to_csv(summaries_dir / filename, index=False)


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------

def build_markdown(df, hide_answers=False):
    """Build the full Markdown document and return as string."""
    buf = io.StringIO()
    redacted_note = "*(answers redacted)*" if hide_answers else None

    _write_header(buf, "Benchmark Analysis", len(df), subtitle=redacted_note)

    # Extra line for multi-model: show model count
    buf.write(f"Models evaluated: {df['model_tag'].nunique() if not df.empty else 0}  \n\n")

    if df.empty:
        buf.write("_No results found. Run benchmarks first:_\n\n")
        buf.write("```\npython -m run_benchmark\n```\n")
        return buf.getvalue()

    write_summaries(buf, df)

    buf.write("\n---\n\n## Per-Prompt Detail\n\n")
    write_per_prompt(buf, df, hide_answers=hide_answers)

    return buf.getvalue()


def build_single_markdown(df):
    """Build a Markdown document for a single model with full responses."""
    buf = io.StringIO()
    model = df["model_tag"].iloc[0] if not df.empty else "Unknown"

    _write_header(buf, f"Benchmark Results — {model}", len(df))

    if df.empty:
        buf.write("_No results found._\n")
        return buf.getvalue()

    _write_model_summary_table(buf, df)
    write_per_prompt(buf, df, hide_answers=False)

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_full_analysis():
    """Generate the redacted + full analysis for all models."""
    results_dir = get_results_dir()
    df = load_all_results()

    for path, hide in [
        (results_dir / "analysis_output.md", True),
        (results_dir / "analysis_output_full.md", False),
    ]:
        content = build_markdown(df, hide_answers=hide)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        label = "Redacted" if hide else "Full"
        print(f"{label} output saved to {path}")


def run_single_view(csv_path_str):
    """Generate a full Markdown file for a single model CSV (gitignored)."""
    csv_path = Path(csv_path_str)
    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}")
        sys.exit(1)

    df = load_result_csv(csv_path)
    if df.empty:
        print(f"Error: no data in {csv_path}")
        sys.exit(1)

    output_path = csv_path.parent / f"{csv_path.stem}_view.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(build_single_markdown(df))
    print(f"Single-model output saved to {output_path}")


def main():
    if "--single" in sys.argv:
        idx = sys.argv.index("--single")
        if idx + 1 >= len(sys.argv):
            print("Usage: python -m run_analysis --single <path-to-csv>")
            sys.exit(1)
        run_single_view(sys.argv[idx + 1])
    else:
        run_full_analysis()


if __name__ == "__main__":
    main()