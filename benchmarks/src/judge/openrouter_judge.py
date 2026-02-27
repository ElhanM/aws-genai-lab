"""Judge backend using the OpenRouter API (OpenAI-compatible).

Recommended model: meta-llama/llama-3.3-70b-instruct

Get an API key at: https://openrouter.ai/keys
"""

import os
import requests

from src.judge.base import JudgeBackend
from src.utils import load_env, load_yaml, setup_logging

load_env()
log = setup_logging("judge.openrouter", "judge.log")

# JSON schema for structured output - mirrors OLLAMA_SCHEMA
OPENROUTER_SCHEMA = {
    "type": "object",
    "required": ["refusal", "accuracy", "utility", "completeness", "reasoning"],
    "properties": {
        "refusal":      {"type": "integer"},
        "accuracy":     {"type": "integer"},
        "utility":      {"type": "integer"},
        "completeness": {"type": "integer"},
        "reasoning":    {"type": "string"},
    },
    "additionalProperties": False,
}


class OpenRouterJudge(JudgeBackend):
    """Judge that uses the OpenRouter API."""

    def __init__(self):
        super().__init__()

        config = load_yaml("judge.yaml")
        openrouter_cfg = config.get("openrouter", {})

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. Add it to your .env file. "
                "Get a key at https://openrouter.ai/keys"
            )

        self.api_key = api_key
        self.model_name = openrouter_cfg.get("model", "meta-llama/llama-3.3-70b-instruct")
        self.temperature = openrouter_cfg.get("temperature", 0.1)
        self.max_output_tokens = openrouter_cfg.get("max_output_tokens", 2048)
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def _call_api(self, system_prompt, user_prompt):
        """Call OpenRouter API with structured JSON schema output and return raw JSON string."""
        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_output_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "judge_scores",
                        "strict": True,
                        "schema": OPENROUTER_SCHEMA,
                    },
                },
            },
            timeout=120,
        )

        # Capture raw body BEFORE raising so it appears in logs
        raw_body = response.text
        if not response.ok:
            raise RuntimeError(
                f"{response.status_code} {response.reason} | {raw_body}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()