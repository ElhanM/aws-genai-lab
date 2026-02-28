import yaml
import logging
from pathlib import Path
from dotenv import load_dotenv


def get_project_root():
    """Return the benchmarks/ directory path."""
    return Path(__file__).parent.parent


def load_yaml(filename):
    """Load a YAML file from the config directory."""
    config_path = get_project_root() / "config" / filename
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_env():
    """Load environment variables from .env file."""
    env_path = get_project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_results_dir():
    """Return the results directory path, creating it if needed."""
    results_dir = get_project_root() / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def get_summaries_dir():
    """Return the summaries directory path, creating it if needed."""
    summaries_dir = get_project_root() / "results" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    return summaries_dir


def get_logs_dir():
    """Return the logs directory path, creating it if needed."""
    logs_dir = get_project_root() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logging(name, log_file=None):
    """Configure logging for a module.

    Log files are overwritten on each run (mode='w') so that logs
    from previous runs do not accumulate.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = get_logs_dir() / log_file
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def sanitize_model_name(tag):
    """Convert a model tag to a safe filename string.

    Handles both Ollama Library tags and HuggingFace GGUF paths.

    Examples:
        'llama3.1:8b'
            -> 'llama3.1_8b'
        'hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF:Q4_K_M'
            -> 'TheBloke_Mistral-7B-Instruct-v0.2-GGUF_Q4_K_M'
        'CognitiveComputations/dolphin-llama3.1:8b'
            -> 'CognitiveComputations_dolphin-llama3.1_8b'
    """
    name = tag

    # Strip the hf.co/ prefix for cleaner filenames
    if name.startswith("hf.co/"):
        name = name[len("hf.co/") :]

    # Replace characters that are unsafe in filenames
    name = name.replace(":", "_").replace("/", "_")

    return name


def normalize_model_tag(tag):
    """Clean up a model tag from config.

    Strips the 'ollama run ' prefix if someone pasted the full
    HuggingFace command from the Ollama website.

    Examples:
        'ollama run hf.co/TheBloke/Mistral:Q4_K_M'
            -> 'hf.co/TheBloke/Mistral:Q4_K_M'
        'llama3.1:8b'
            -> 'llama3.1:8b'
    """
    cleaned = tag.strip()
    if cleaned.lower().startswith("ollama run "):
        cleaned = cleaned[len("ollama run ") :].strip()
    return cleaned
