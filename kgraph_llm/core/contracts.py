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
    dataset_joins: tuple[dict[str, Any], ...]
    registry_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SQLProposal:
    sql: str
    parameters: tuple[Any, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class SemanticQueryPlan:
    """Provider-neutral, non-SQL analytical plan constrained by K-Graph metadata."""

    operation: str
    datasets: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    filters: tuple[dict[str, Any], ...] = ()
    calculations: tuple[dict[str, Any], ...] = ()
    time_bucket: dict[str, Any] = field(default_factory=dict)
    window_calculations: tuple[dict[str, Any], ...] = ()
    statistics: tuple[dict[str, Any], ...] = ()
    data_quality_checks: tuple[dict[str, Any], ...] = ()
    graph_query: dict[str, Any] = field(default_factory=dict)
    transform: str = "none"
    comparison: dict[str, Any] = field(default_factory=dict)
    order_by: tuple[dict[str, str], ...] = ()
    start_year: int | None = None
    end_year: int | None = None
    result_limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticQueryPlan:
        return cls(
            operation=str(data.get("operation", "")),
            datasets=tuple(str(value) for value in (data.get("datasets") or [])),
            dimensions=tuple(str(value) for value in (data.get("dimensions") or [])),
            metrics=tuple(str(value) for value in (data.get("metrics") or [])),
            fields=tuple(str(value) for value in (data.get("fields") or [])),
            filters=tuple(dict(value) for value in (data.get("filters") or [])),
            calculations=tuple(
                dict(value) for value in (data.get("calculations") or [])
            ),
            time_bucket=dict(data.get("time_bucket") or {}),
            window_calculations=tuple(
                dict(value) for value in (data.get("window_calculations") or [])
            ),
            statistics=tuple(
                dict(value) for value in (data.get("statistics") or [])
            ),
            data_quality_checks=tuple(
                dict(value) for value in (data.get("data_quality_checks") or [])
            ),
            graph_query=dict(data.get("graph_query") or {}),
            transform=str(data.get("transform", "none")),
            comparison=dict(data.get("comparison") or {}),
            order_by=tuple(dict(value) for value in (data.get("order_by") or [])),
            start_year=data.get("start_year"),
            end_year=data.get("end_year"),
            result_limit=data.get("result_limit"),
        )


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
