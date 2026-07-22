from __future__ import annotations

from typing import Protocol

from ..core.contracts import GraphContext, QuestionSpec, SemanticQueryPlan
from .definition import GraphDefinition


class SemanticGraphRepository(Protocol):
    def retrieve(self, spec: QuestionSpec) -> GraphContext: ...

    def allowed_datasets(self) -> set[str]: ...

    def execute_graph_plan(
        self, plan: SemanticQueryPlan, context: GraphContext, *, row_limit: int
    ) -> tuple[dict[str, object], ...]: ...

    def verify_connectivity(self) -> None: ...

    def bootstrap(self, definitions: tuple[GraphDefinition, ...], *, reset: bool = False) -> None: ...

    def close(self) -> None: ...
