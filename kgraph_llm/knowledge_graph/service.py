from __future__ import annotations

import os
from pathlib import Path

from .base import SemanticGraphRepository
from .definition import GraphDefinition
from .networkx_repository import NetworkXSemanticGraph


DEFAULT_GRAPH_PATH = Path("var/knowledge_graph.json")


def graph_path_from_env() -> Path:
    return Path(os.environ.get("KGRAPH_PATH", str(DEFAULT_GRAPH_PATH)))


def make_knowledge_graph_from_env() -> SemanticGraphRepository:
    return NetworkXSemanticGraph.load(graph_path_from_env())


def initialize_knowledge_graph_from_env(
    definitions: tuple[GraphDefinition, ...],
    *,
    reset: bool = False,
) -> NetworkXSemanticGraph:
    repository = NetworkXSemanticGraph(path=graph_path_from_env())
    repository.bootstrap(definitions, reset=reset)
    repository.save()
    return repository
