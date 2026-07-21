from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuestionSpec:
    original_question: str
    purpose: str = "exploratory_analysis"
    consequence_class: str = "low"
    entity_type: str = ""
    metric_terms: tuple[str, ...] = ()
    comparison: str = ""
    start_year: int | None = None
    end_year: int | None = None
    filters: dict[str, str] = field(default_factory=dict)
    defaulted_fields: tuple[str, ...] = ()
    ambiguity_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticDataset:
    name: str
    description: str
    grain: str
    fields: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class GraphContext:
    entities: tuple[str, ...]
    datasets: tuple[SemanticDataset, ...]
    metrics: tuple[dict[str, str], ...]
    relationships: tuple[dict[str, str], ...]
    registry_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SQLProposal:
    sql: str
    parameters: tuple[Any, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class QueryOutcome:
    status: str
    assurance: str
    question_spec: QuestionSpec
    graph_context: GraphContext | None = None
    sql: str | None = None
    parameters: tuple[Any, ...] = ()
    rows: tuple[dict[str, Any], ...] = ()
    findings: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
