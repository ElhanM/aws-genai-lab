"""Scoring utilities for aggregating and comparing benchmark results."""

import pandas as pd

from src.utils import get_results_dir, setup_logging

log = setup_logging("scoring", "scoring.log")


def load_result_csv(filepath):
    """Load a single model result CSV into a DataFrame."""
    try:
        df = pd.read_csv(filepath)
        log.info("Loaded %s (%d rows)", filepath, len(df))
        return df
    except Exception as exc:
        log.error("Failed to load %s: %s", filepath, exc)
        return pd.DataFrame()


def load_all_results():
    """Load all CSV files from the results directory into a single DataFrame.

    Only loads CSVs directly in results/ (not in subdirectories like summaries/).
    """
    results_dir = get_results_dir()
    csv_files = sorted(f for f in results_dir.glob("*.csv") if f.is_file())

    if not csv_files:
        log.warning("No CSV files found in %s", results_dir)
        return pd.DataFrame()

    frames = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            frames.append(df)
            log.info("Loaded %s (%d rows)", csv_file.name, len(df))
        except Exception as exc:
            log.error("Failed to load %s: %s", csv_file.name, exc)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def compute_model_summary(df):
    """Compute per-model aggregate scores.

    Returns a DataFrame with one row per model containing mean scores
    across all criteria and an overall_score (mean of the four criteria).
    """
    if df.empty:
        return pd.DataFrame()

    score_cols = ["refusal", "accuracy", "utility", "completeness"]
    existing_cols = [c for c in score_cols if c in df.columns]

    if not existing_cols:
        log.warning("No score columns found in data")
        return pd.DataFrame()

    summary = df.groupby("model_tag")[existing_cols].mean().round(2)
    summary["overall_score"] = summary[existing_cols].mean(axis=1).round(2)
    summary = summary.sort_values("overall_score", ascending=False)
    summary = summary.reset_index()

    return summary


def compute_difficulty_breakdown(df):
    """Compute per-model, per-difficulty aggregate scores.

    Returns a DataFrame grouped by model_tag and difficulty.
    """
    if df.empty:
        return pd.DataFrame()

    score_cols = ["refusal", "accuracy", "utility", "completeness"]
    existing_cols = [c for c in score_cols if c in df.columns]

    if not existing_cols:
        return pd.DataFrame()

    breakdown = df.groupby(["model_tag", "difficulty"])[existing_cols].mean().round(2)
    breakdown["overall_score"] = breakdown[existing_cols].mean(axis=1).round(2)
    breakdown = breakdown.reset_index()

    return breakdown


def compute_category_breakdown(df):
    """Compute per-model, per-category aggregate scores."""
    if df.empty:
        return pd.DataFrame()

    score_cols = ["refusal", "accuracy", "utility", "completeness"]
    existing_cols = [c for c in score_cols if c in df.columns]

    if not existing_cols:
        return pd.DataFrame()

    breakdown = df.groupby(["model_tag", "category"])[existing_cols].mean().round(2)
    breakdown["overall_score"] = breakdown[existing_cols].mean(axis=1).round(2)
    breakdown = breakdown.reset_index()

    return breakdown
