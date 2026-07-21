# NetworkX semantic K-Graph

NetworkX is the pilot's embedded semantic K-Graph. SQLite remains the analytical database and contains Health facts, approved analytical views, and execution audit records. The LLM receives governed graph context rather than discovering arbitrary SQLite schema.

## Property-graph model

The graph is a directed multigraph. Nodes have a `kind` property:

- `SemanticEntity`
- `SemanticDataset`
- `SemanticField`
- `SemanticMetric`
- `SemanticAlias`
- `RegistryMetadata`

Edges have a `relation` property:

- `ALIASES`: language term to entity or metric
- `AVAILABLE_IN`: entity or metric to approved dataset
- `HAS_FIELD`: dataset to governed field
- `DEFINED_ON`: metric to its defining dataset
- `SEMANTIC_RELATION`: entity-to-entity meaning and governed join guidance

The query pipeline traverses aliases and `AVAILABLE_IN` edges to select relevant analytical datasets. It retrieves their fields, metrics, and entity relations before asking the LLM to propose SQL.

## Persistence and commands

The default file is `var/knowledge_graph.json`, using NetworkX's node-link JSON representation. Override it with `KGRAPH_PATH`.

```bash
python3 -m kerala_kg_llm graph-init
python3 -m kerala_kg_llm graph-status
```

`graph-init` deterministically rebuilds the file from active definitions in `ministries/registry.py`. Graph metadata is not mixed into the analytical SQLite database.

## Ministry ownership

Health owns its declaration in `ministries/health/graph_definition.py`. The shared repository understands only generic node and edge contracts. Future ministries supply a versioned graph definition and activate it through the central ministry registry.

## Scope limit

This behaves as a graph for traversal and relationship retrieval, but it is embedded and loaded into one Python process. It does not provide a server, concurrent transactional writes, database-native authorization, or distributed scaling. Those are production migration concerns, not requirements for the local pilot.
