from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from ..core.contracts import GraphContext, QuestionSpec, SemanticDataset
from .definition import GraphDefinition


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _node_id(kind: str, name: str) -> str:
    return f"{kind}:{name}"


class NetworkXSemanticGraph:
    """Embedded property graph with optional JSON persistence."""

    FORMAT_VERSION = 1

    def __init__(
        self,
        graph: nx.MultiDiGraph | None = None,
        *,
        path: Path | None = None,
    ) -> None:
        self.graph = graph if graph is not None else nx.MultiDiGraph()
        self.path = path

    @classmethod
    def from_definitions(
        cls,
        definitions: tuple[GraphDefinition, ...],
        *,
        path: Path | None = None,
    ) -> NetworkXSemanticGraph:
        repository = cls(path=path)
        repository.bootstrap(definitions)
        return repository

    @classmethod
    def load(cls, path: Path) -> NetworkXSemanticGraph:
        if not path.exists():
            raise RuntimeError(
                f"NetworkX K-Graph not found at {path}. Run: python -m kgraph_llm graph-init"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            graph = json_graph.node_link_graph(payload, edges="edges")
        except (OSError, ValueError, nx.NetworkXError) as exc:
            raise RuntimeError(f"Could not load NetworkX K-Graph at {path}: {exc}") from exc
        if not isinstance(graph, nx.MultiDiGraph):
            graph = nx.MultiDiGraph(graph)
        return cls(graph, path=path)

    def save(self, path: Path | None = None) -> Path:
        destination = path or self.path
        if destination is None:
            raise ValueError("A graph path is required to persist the NetworkX K-Graph.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json_graph.node_link_data(self.graph, edges="edges")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        self.path = destination
        return destination

    def verify_connectivity(self) -> None:
        if self.graph.graph.get("format_version") != self.FORMAT_VERSION:
            raise RuntimeError("Unsupported or missing NetworkX K-Graph format version.")
        if self.graph.number_of_nodes() == 0:
            raise RuntimeError("The NetworkX K-Graph is empty. Run graph-init.")

    def close(self) -> None:
        return None

    def stats(self) -> dict[str, Any]:
        kinds = Counter(
            str(attributes.get("kind", "Unknown"))
            for _, attributes in self.graph.nodes(data=True)
        )
        return {
            "path": str(self.path) if self.path else None,
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_kinds": dict(sorted(kinds.items())),
        }

    def bootstrap(
        self,
        definitions: tuple[GraphDefinition, ...],
        *,
        reset: bool = False,
    ) -> None:
        # Definitions are the source of truth, so a rebuild is deterministic and
        # prevents deleted ministry metadata from lingering in the persisted graph.
        del reset
        graph = nx.MultiDiGraph(format_version=self.FORMAT_VERSION)

        for definition in definitions:
            ministry = definition.ministry
            metadata_id = _node_id("metadata", f"registry_version:{ministry}")
            graph.add_node(
                metadata_id,
                kind="RegistryMetadata",
                key=f"registry_version:{ministry}",
                value=definition.registry_version,
                ministry=ministry,
            )

            for entity in definition.entities:
                graph.add_node(
                    _node_id("entity", entity["name"]),
                    kind="SemanticEntity",
                    ministry=ministry,
                    **entity,
                )

            for dataset in definition.datasets:
                dataset_id = _node_id("dataset", dataset["name"])
                graph.add_node(
                    dataset_id,
                    kind="SemanticDataset",
                    name=dataset["name"],
                    description=dataset["description"],
                    grain=dataset["grain"],
                    governed=bool(dataset["governed"]),
                    ministry=ministry,
                )
                for field in dataset["fields"]:
                    field_key = f"{dataset['name']}.{field['column_name']}"
                    field_id = _node_id("field", field_key)
                    graph.add_node(
                        field_id,
                        kind="SemanticField",
                        key=field_key,
                        ministry=ministry,
                        **field,
                    )
                    graph.add_edge(dataset_id, field_id, relation="HAS_FIELD")

            for metric in definition.metrics:
                metric_id = _node_id("metric", metric["name"])
                dataset_id = _node_id("dataset", metric["dataset_name"])
                graph.add_node(
                    metric_id,
                    kind="SemanticMetric",
                    ministry=ministry,
                    **metric,
                )
                graph.add_edge(metric_id, dataset_id, relation="DEFINED_ON")

            for relationship in definition.relationships:
                graph.add_edge(
                    _node_id("entity", relationship["from_entity"]),
                    _node_id("entity", relationship["to_entity"]),
                    relation="SEMANTIC_RELATION",
                    ministry=ministry,
                    **relationship,
                )

            for alias in definition.aliases:
                alias_key = (
                    f"{ministry}:{alias['term']}:{alias['target_type']}:{alias['target_name']}"
                )
                alias_id = _node_id("alias", alias_key)
                target_id = _node_id(alias["target_type"], alias["target_name"])
                graph.add_node(
                    alias_id,
                    kind="SemanticAlias",
                    key=alias_key,
                    ministry=ministry,
                    **alias,
                )
                graph.add_edge(alias_id, target_id, relation="ALIASES")

            for link in definition.dataset_links:
                dataset_id = _node_id("dataset", link["dataset_name"])
                graph.add_edge(
                    _node_id("entity", link["entity_name"]),
                    dataset_id,
                    relation="AVAILABLE_IN",
                )
                graph.add_edge(
                    _node_id("metric", link["metric_name"]),
                    dataset_id,
                    relation="AVAILABLE_IN",
                )

        self.graph = graph

    def allowed_datasets(self) -> set[str]:
        return {
            str(attributes["name"])
            for _, attributes in self.graph.nodes(data=True)
            if attributes.get("kind") == "SemanticDataset"
            and attributes.get("governed") is True
        }

    def retrieve(self, spec: QuestionSpec) -> GraphContext:
        terms = _tokens(spec.original_question)
        terms.update(term.lower() for term in spec.metric_terms)
        if spec.entity_type:
            terms.add(spec.entity_type.lower())

        entities: set[str] = set()
        metrics: set[str] = set(spec.metric_terms)
        for node_id, attributes in self.graph.nodes(data=True):
            if attributes.get("kind") != "SemanticAlias":
                continue
            if str(attributes.get("term", "")).lower() not in terms:
                continue
            for _, target_id, edge in self.graph.out_edges(node_id, data=True):
                if edge.get("relation") != "ALIASES":
                    continue
                target = self.graph.nodes[target_id]
                if target.get("kind") == "SemanticEntity":
                    entities.add(str(target["name"]))
                elif target.get("kind") == "SemanticMetric":
                    metrics.add(str(target["name"]))
        if spec.entity_type:
            entities.add(spec.entity_type)

        dataset_names: set[str] = set()
        for name in entities:
            node_id = _node_id("entity", name)
            if node_id in self.graph:
                dataset_names.update(self._available_datasets(node_id))
        for name in metrics:
            node_id = _node_id("metric", name)
            if node_id in self.graph:
                dataset_names.update(self._available_datasets(node_id))

        datasets: list[SemanticDataset] = []
        for name in sorted(dataset_names):
            dataset_id = _node_id("dataset", name)
            attributes = self.graph.nodes[dataset_id]
            if attributes.get("governed") is not True:
                continue
            fields: list[dict[str, str]] = []
            field_nodes = [
                self.graph.nodes[target]
                for _, target, edge in self.graph.out_edges(dataset_id, data=True)
                if edge.get("relation") == "HAS_FIELD"
            ]
            for field in sorted(field_nodes, key=lambda item: int(item["ordinal"])):
                fields.append(
                    {
                        "column_name": str(field["column_name"]),
                        "semantic_role": str(field["semantic_role"]),
                        "data_type": str(field["data_type"]),
                        "description": str(field["description"]),
                    }
                )
            datasets.append(
                SemanticDataset(
                    name=name,
                    description=str(attributes["description"]),
                    grain=str(attributes["grain"]),
                    fields=tuple(fields),
                )
            )

        metric_rows: list[dict[str, str]] = []
        for name in sorted(metrics):
            node_id = _node_id("metric", name)
            if node_id not in self.graph:
                continue
            attributes = self.graph.nodes[node_id]
            metric_rows.append(
                {
                    key: str(attributes[key])
                    for key in (
                        "name",
                        "dataset_name",
                        "expression",
                        "aggregation",
                        "description",
                    )
                }
            )

        relationship_rows: list[dict[str, str]] = []
        for source, target, edge in self.graph.edges(data=True):
            if edge.get("relation") != "SEMANTIC_RELATION":
                continue
            source_name = str(self.graph.nodes[source]["name"])
            target_name = str(self.graph.nodes[target]["name"])
            if source_name not in entities and target_name not in entities:
                continue
            relationship_rows.append(
                {
                    "from_entity": source_name,
                    "predicate": str(edge["predicate"]),
                    "to_entity": target_name,
                    "join_expression": str(edge["join_expression"]),
                    "description": str(edge["description"]),
                }
            )
        relationship_rows.sort(
            key=lambda row: (row["from_entity"], row["predicate"], row["to_entity"])
        )

        versions = sorted(
            (
                str(attributes["key"]),
                str(attributes["value"]),
            )
            for _, attributes in self.graph.nodes(data=True)
            if attributes.get("kind") == "RegistryMetadata"
            and str(attributes.get("key", "")).startswith("registry_version:")
        )
        return GraphContext(
            entities=tuple(sorted(entities)),
            datasets=tuple(datasets),
            metrics=tuple(metric_rows),
            relationships=tuple(relationship_rows),
            registry_version="+".join(value for _, value in versions),
        )

    def _available_datasets(self, node_id: str) -> set[str]:
        return {
            str(self.graph.nodes[target]["name"])
            for _, target, edge in self.graph.out_edges(node_id, data=True)
            if edge.get("relation") == "AVAILABLE_IN"
            and self.graph.nodes[target].get("kind") == "SemanticDataset"
        }
