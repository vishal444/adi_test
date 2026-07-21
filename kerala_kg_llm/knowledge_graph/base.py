from __future__ import annotations

from typing import Protocol

from ..core.contracts import GraphContext, QuestionSpec
from .definition import GraphDefinition


class SemanticGraphRepository(Protocol):
    def retrieve(self, spec: QuestionSpec) -> GraphContext: ...

    def allowed_datasets(self) -> set[str]: ...

    def verify_connectivity(self) -> None: ...

    def bootstrap(self, definitions: tuple[GraphDefinition, ...], *, reset: bool = False) -> None: ...

    def close(self) -> None: ...
