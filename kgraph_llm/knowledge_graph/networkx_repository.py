from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from ..core.contracts import (
    GraphContext,
    QuestionSpec,
    SemanticDataset,
    SemanticQueryPlan,
)
from .definition import GraphDefinition


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _node_id(kind: str, name: str) -> str:
    return f"{kind}:{name}"


class NetworkXSemanticGraph:
    """Embedded property graph with optional JSON persistence."""

    FORMAT_VERSION = 2

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

            for join in definition.dataset_joins:
                graph.add_edge(
                    _node_id("dataset", join["left_dataset"]),
                    _node_id("dataset", join["right_dataset"]),
                    relation="DATASET_JOIN",
                    ministry=ministry,
                    **join,
                )

        self.graph = graph

    def allowed_datasets(self) -> set[str]:
        return {
            str(attributes["name"])
            for _, attributes in self.graph.nodes(data=True)
            if attributes.get("kind") == "SemanticDataset"
            and attributes.get("governed") is True
        }

    def execute_graph_plan(
        self,
        plan: SemanticQueryPlan,
        context: GraphContext,
        *,
        row_limit: int,
    ) -> tuple[dict[str, object], ...]:
        """Execute a bounded, non-mutating graph path or neighborhood plan."""
        if plan.operation != "graph":
            raise ValueError("PLAN_INVALID: graph execution requires operation=graph.")
        if (
            plan.datasets
            or plan.metrics
            or plan.fields
            or plan.dimensions
            or plan.filters
            or plan.calculations
            or plan.time_bucket
            or plan.window_calculations
            or plan.statistics
            or plan.data_quality_checks
            or plan.transform != "none"
            or plan.comparison
            or plan.order_by
            or plan.start_year is not None
            or plan.end_year is not None
        ):
            raise ValueError("PLAN_INVALID: graph plans cannot project relational data.")
        if plan.result_limit is not None and (
            not isinstance(plan.result_limit, int)
            or isinstance(plan.result_limit, bool)
            or not 1 <= plan.result_limit <= 10_000
        ):
            raise ValueError("PLAN_INVALID: graph result_limit must be between 1 and 10000.")
        query = plan.graph_query
        operator = str(query.get("operator", ""))
        if operator not in {"graph_path", "graph_neighborhood"}:
            raise ValueError("PLAN_INVALID: unsupported graph operator.")
        direction = str(query.get("direction", "outgoing"))
        if direction not in {"outgoing", "incoming", "undirected"}:
            raise ValueError("PLAN_INVALID: graph direction is not allowed.")
        max_depth = query.get("max_depth", 5 if operator == "graph_path" else 2)
        depth_limit = 20 if operator == "graph_path" else 5
        if (
            not isinstance(max_depth, int)
            or isinstance(max_depth, bool)
            or not 1 <= max_depth <= depth_limit
        ):
            raise ValueError(
                f"PLAN_INVALID: graph max_depth must be between 1 and {depth_limit}."
            )
        allowed_edges = {
            "SEMANTIC_RELATION",
            "AVAILABLE_IN",
            "DEFINED_ON",
            "HAS_FIELD",
            "DATASET_JOIN",
        }
        requested_edges = query.get("edge_types") or sorted(allowed_edges)
        if not isinstance(requested_edges, list) or not requested_edges:
            raise ValueError("PLAN_INVALID: edge_types must be a non-empty array.")
        edge_types = {str(value) for value in requested_edges}
        if not edge_types.issubset(allowed_edges):
            raise ValueError("PLAN_INVALID: graph plan requested an unapproved edge type.")

        traversal = nx.DiGraph()
        for source, target, attributes in self.graph.edges(data=True):
            if attributes.get("relation") not in edge_types:
                continue
            traversal.add_edge(source, target)
        if direction == "incoming":
            traversal = traversal.reverse(copy=False)
        elif direction == "undirected":
            traversal = traversal.to_undirected(as_view=True)

        context_names = self._context_graph_names(context)
        start = self._resolve_graph_node(
            str(query.get("start", "")),
            str(query.get("start_kind", "")),
            context_names,
        )
        if start not in traversal:
            return ()
        if operator == "graph_path":
            end = self._resolve_graph_node(
                str(query.get("end", "")),
                str(query.get("end_kind", "")),
                context_names,
            )
            try:
                path = nx.shortest_path(traversal, start, end)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return ()
            if len(path) - 1 > max_depth:
                return ()
            raw_rows = [
                self._graph_edge_row(source, target, step, direction, edge_types)
                for step, (source, target) in enumerate(zip(path, path[1:]), start=1)
            ]
        else:
            lengths = nx.single_source_shortest_path_length(
                traversal, start, cutoff=max_depth
            )
            node_kinds = query.get("node_kinds") or []
            if not isinstance(node_kinds, list):
                raise ValueError("PLAN_INVALID: node_kinds must be an array.")
            allowed_kinds = {str(value) for value in node_kinds}
            raw_rows = []
            for node, distance in lengths.items():
                if node == start:
                    continue
                attributes = self.graph.nodes[node]
                if allowed_kinds and str(attributes.get("kind", "")) not in allowed_kinds:
                    continue
                raw_rows.append(
                    {
                        "node_name": self._graph_node_name(node),
                        "node_kind": str(attributes.get("kind", "Unknown")),
                        "distance": int(distance),
                    }
                )
            raw_rows.sort(key=lambda row: (int(row["distance"]), str(row["node_kind"]), str(row["node_name"])))

        total = len(raw_rows)
        semantic_limit = plan.result_limit or row_limit
        actual_limit = min(row_limit, semantic_limit)
        if operator == "graph_path" and total > actual_limit:
            raise ValueError(
                "GRAPH_RESULT_LIMIT: the complete path exceeds the governed result limit."
            )
        return tuple(
            row | {"_total_rows": total, "_result_rank": rank}
            for rank, row in enumerate(raw_rows[:actual_limit], start=1)
        )

    @staticmethod
    def _context_graph_names(context: GraphContext) -> set[str]:
        names = set(context.entities)
        names.update(dataset.name for dataset in context.datasets)
        names.update(str(metric["name"]) for metric in context.metrics)
        for relationship in context.relationships:
            names.add(str(relationship["from_entity"]))
            names.add(str(relationship["to_entity"]))
        return names

    def _resolve_graph_node(
        self, name: str, kind: str, context_names: set[str]
    ) -> str:
        if not name:
            raise ValueError("PLAN_INVALID: graph node name is required.")
        if name not in context_names:
            raise ValueError(
                f"PLAN_INVALID: graph node {name!r} is outside the retrieved graph context."
            )
        kind_aliases = {
            "entity": "SemanticEntity",
            "dataset": "SemanticDataset",
            "field": "SemanticField",
            "metric": "SemanticMetric",
            "alias": "SemanticAlias",
            "metadata": "RegistryMetadata",
        }
        normalized_kind = kind_aliases.get(kind.casefold(), kind) if kind else ""
        candidates = []
        for node_id, attributes in self.graph.nodes(data=True):
            node_name = str(attributes.get("name", attributes.get("key", "")))
            if node_name != name:
                continue
            if normalized_kind and str(attributes.get("kind", "")) != normalized_kind:
                continue
            candidates.append(node_id)
        if len(candidates) != 1:
            raise ValueError(
                f"PLAN_INVALID: graph node {name!r} is absent or ambiguous; provide its exact kind."
            )
        return candidates[0]

    def _graph_edge_row(
        self,
        traversal_source: str,
        traversal_target: str,
        step: int,
        direction: str,
        edge_types: set[str],
    ) -> dict[str, object]:
        source, target = traversal_source, traversal_target
        edge_rows = self.graph.get_edge_data(source, target, default={}).values()
        if direction in {"incoming", "undirected"} and not any(
            row.get("relation") in edge_types for row in edge_rows
        ):
            source, target = target, source
            edge_rows = self.graph.get_edge_data(source, target, default={}).values()
        attributes = next(
            (
                row
                for row in sorted(
                    edge_rows,
                    key=lambda value: (
                        str(value.get("relation", "")),
                        str(value.get("predicate", "")),
                    ),
                )
                if row.get("relation") in edge_types
            ),
            None,
        )
        if attributes is None:
            raise ValueError("QUERY_RESULT_INVALID: graph path edge metadata is missing.")
        return {
            "step": step,
            "source_name": self._graph_node_name(source),
            "source_kind": str(self.graph.nodes[source].get("kind", "Unknown")),
            "relation": str(attributes.get("predicate", attributes.get("relation", ""))),
            "target_name": self._graph_node_name(target),
            "target_kind": str(self.graph.nodes[target].get("kind", "Unknown")),
            "description": str(attributes.get("description", "")),
        }

    def _graph_node_name(self, node_id: str) -> str:
        attributes = self.graph.nodes[node_id]
        return str(attributes.get("name", attributes.get("key", node_id)))

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
            canonical_entities = [
                str(attributes["name"])
                for _, attributes in self.graph.nodes(data=True)
                if attributes.get("kind") == "SemanticEntity"
                and str(attributes.get("name", "")).casefold()
                == spec.entity_type.casefold()
            ]
            entities.add(
                canonical_entities[0]
                if len(canonical_entities) == 1
                else spec.entity_type
            )

        # Include semantic entities on the shortest connecting paths between
        # explicitly retrieved endpoints so the planner sees the relations it
        # may request; execution is still bounded and validated separately.
        if len(entities) >= 2:
            entity_graph = nx.Graph()
            for source, target, edge in self.graph.edges(data=True):
                if edge.get("relation") == "SEMANTIC_RELATION":
                    entity_graph.add_edge(source, target)
            selected = sorted(entities)
            for index, left_name in enumerate(selected):
                for right_name in selected[index + 1 :]:
                    try:
                        path = nx.shortest_path(
                            entity_graph,
                            _node_id("entity", left_name),
                            _node_id("entity", right_name),
                        )
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue
                    entities.update(
                        str(self.graph.nodes[node]["name"])
                        for node in path
                        if self.graph.nodes[node].get("kind") == "SemanticEntity"
                    )

        dataset_names: set[str] = set()
        metric_dataset_names: set[str] = set()
        for name in metrics:
            node_id = _node_id("metric", name)
            if node_id in self.graph:
                metric_dataset_names.update(self._available_datasets(node_id))
        if metric_dataset_names:
            dataset_names.update(metric_dataset_names)
        else:
            for name in entities:
                node_id = _node_id("entity", name)
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
                | {
                    key: str(attributes[key])
                    for key in (
                        "unit",
                        "additivity",
                        "entity_key",
                        "time_field",
                        "valid_transforms",
                        "zero_policy",
                    )
                    if key in attributes
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

        join_rows: list[dict[str, Any]] = []
        for source, target, edge in self.graph.edges(data=True):
            if edge.get("relation") != "DATASET_JOIN":
                continue
            left_name = str(self.graph.nodes[source]["name"])
            right_name = str(self.graph.nodes[target]["name"])
            if left_name not in dataset_names or right_name not in dataset_names:
                continue
            join_rows.append(
                {
                    "left_dataset": left_name,
                    "right_dataset": right_name,
                    "keys": [list(pair) for pair in edge.get("keys", ())],
                    "cardinality": str(edge.get("cardinality", "")),
                    "description": str(edge.get("description", "")),
                }
            )
        join_rows.sort(key=lambda row: (row["left_dataset"], row["right_dataset"]))

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
            dataset_joins=tuple(join_rows),
            registry_version="+".join(value for _, value in versions),
        )

    def _available_datasets(self, node_id: str) -> set[str]:
        return {
            str(self.graph.nodes[target]["name"])
            for _, target, edge in self.graph.out_edges(node_id, data=True)
            if edge.get("relation") == "AVAILABLE_IN"
            and self.graph.nodes[target].get("kind") == "SemanticDataset"
        }
