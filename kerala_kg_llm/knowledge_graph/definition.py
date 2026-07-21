from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphDefinition:
    """A ministry-owned, versioned set of semantic nodes and relationships."""

    ministry: str
    registry_version: str
    entities: tuple[dict[str, Any], ...]
    datasets: tuple[dict[str, Any], ...]
    metrics: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    aliases: tuple[dict[str, Any], ...]
    dataset_links: tuple[dict[str, Any], ...]
