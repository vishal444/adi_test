from __future__ import annotations

import os
import re
from pathlib import Path

from .base import LLMAdapter
from .google_provider import GoogleGeminiLLM
from .openai_provider import OpenAIResponsesLLM


_ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_project_environment() -> None:
    """Load simple KEY=VALUE entries from cwd/.env without overriding the shell."""
    path = Path.cwd() / ".env"
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Could not read environment file {path}: {exc}") from exc
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"Invalid .env entry on line {line_number}.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not _ENVIRONMENT_KEY.fullmatch(key):
            raise ValueError(f"Invalid .env key on line {line_number}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def make_llm(provider: str) -> LLMAdapter:
    if provider == "local":
        # The local adapter is deliberately domain-specific and lives with Health.
        from ..ministries.health.local_llm import LocalHealthDemoLLM

        return LocalHealthDemoLLM()
    if provider == "openai":
        _load_project_environment()
        return OpenAIResponsesLLM()
    if provider in {"google", "gemini"}:
        _load_project_environment()
        return GoogleGeminiLLM()
    raise ValueError(f"Unknown provider: {provider}")
