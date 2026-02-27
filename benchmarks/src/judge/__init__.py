"""Judge package - factory and re-exports."""

from src.judge.base import JudgeBackend
from src.utils import load_yaml


def create_judge():
    """Create the appropriate judge backend based on config."""
    config = load_yaml("judge.yaml")
    backend = config.get("backend", "openrouter")

    if backend == "openrouter":
        from src.judge.openrouter_judge import OpenRouterJudge
        return OpenRouterJudge()
    else:
        raise ValueError(
            f"Unknown judge backend: '{backend}'. "
        "Set backend to 'openrouter' in config/judge.yaml."
        )