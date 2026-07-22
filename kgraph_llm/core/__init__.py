"""Shared contracts that cross component and ministry boundaries."""

from .contracts import (
    GraphContext,
    QueryOutcome,
    QuestionSpec,
    SQLProposal,
    SemanticDataset,
    SemanticQueryPlan,
)

__all__ = [
    "GraphContext",
    "QueryOutcome",
    "QuestionSpec",
    "SQLProposal",
    "SemanticDataset",
    "SemanticQueryPlan",
]
