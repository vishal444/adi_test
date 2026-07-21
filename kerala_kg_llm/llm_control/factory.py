from __future__ import annotations

from .base import LLMAdapter
from .openai_provider import OpenAIResponsesLLM


def make_llm(provider: str) -> LLMAdapter:
    if provider == "local":
        # The local adapter is deliberately domain-specific and lives with Health.
        from ..ministries.health.local_llm import LocalHealthDemoLLM

        return LocalHealthDemoLLM()
    if provider == "openai":
        return OpenAIResponsesLLM()
    raise ValueError(f"Unknown provider: {provider}")

