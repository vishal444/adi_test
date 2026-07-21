from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..knowledge_graph.definition import GraphDefinition
from .health.graph_definition import GRAPH_DEFINITION as HEALTH_GRAPH_DEFINITION


MINISTRIES_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class MinistryModule:
    code: str
    display_name: str
    status: str
    description: str
    bootstrap_scripts: tuple[Path, ...] = ()
    graph_definition: GraphDefinition | None = None

    @property
    def active(self) -> bool:
        return self.status == "active_pilot"


HEALTH_ROOT = MINISTRIES_ROOT / "health"

MINISTRIES = (
    MinistryModule(
        code="health",
        display_name="Health",
        status="active_pilot",
        description="Hospital funding and service-output analytical pilot.",
        bootstrap_scripts=(
            HEALTH_ROOT / "sql" / "schema.sql",
            HEALTH_ROOT / "sql" / "demo_seed.sql",
        ),
        graph_definition=HEALTH_GRAPH_DEFINITION,
    ),
    MinistryModule("education", "Education", "scaffold", "Reserved for institution, enrollment, attendance, assessment, staffing, and funding data."),
    MinistryModule("finance", "Finance", "scaffold", "Reserved for budget, expenditure, payment, and revenue data."),
    MinistryModule("procurement", "Procurement", "scaffold", "Reserved for tenders, bids, awards, amendments, vendors, and contract performance."),
    MinistryModule("law_enforcement", "Law Enforcement", "scaffold", "Reserved for purpose-restricted agency, incident, case, and explicit role data."),
    MinistryModule("transport", "Transport", "scaffold", "Reserved for routes, ridership, traffic, incidents, and maintenance data."),
    MinistryModule("welfare", "Welfare", "scaffold", "Reserved for programs, eligibility, participation, coverage, and benefit data."),
)


def active_ministries() -> tuple[MinistryModule, ...]:
    return tuple(ministry for ministry in MINISTRIES if ministry.active)


def active_graph_definitions() -> tuple[GraphDefinition, ...]:
    return tuple(
        ministry.graph_definition
        for ministry in active_ministries()
        if ministry.graph_definition is not None
    )
