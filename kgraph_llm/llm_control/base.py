from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.contracts import GraphContext, QuestionSpec, SemanticQueryPlan


class LLMError(RuntimeError):
    pass


class LLMAdapter(ABC):
    """Provider-neutral contract for interpretation and non-SQL semantic planning."""

    name = "abstract"

    @abstractmethod
    def interpret(self, question: str) -> QuestionSpec:
        raise NotImplementedError

    @abstractmethod
    def plan_query(self, spec: QuestionSpec, context: GraphContext) -> SemanticQueryPlan:
        """Return a constrained semantic plan, never SQL."""
        raise NotImplementedError
