from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..core.contracts import GraphContext, QuestionSpec, SQLProposal


class LLMError(RuntimeError):
    pass


class LLMAdapter(ABC):
    """Provider-neutral contract for the three bounded LLM stages."""

    name = "abstract"

    @abstractmethod
    def interpret(self, question: str) -> QuestionSpec:
        raise NotImplementedError

    @abstractmethod
    def generate_sql(self, spec: QuestionSpec, context: GraphContext) -> SQLProposal:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, spec: QuestionSpec, rows: tuple[dict[str, Any], ...]) -> str:
        raise NotImplementedError

