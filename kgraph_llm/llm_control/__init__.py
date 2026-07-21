"""Provider-neutral LLM interfaces, providers, and construction."""

from .base import LLMAdapter, LLMError
from .factory import make_llm

__all__ = ["LLMAdapter", "LLMError", "make_llm"]

