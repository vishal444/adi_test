# Project structure

The repository is organized around stable platform controls and independently owned ministry modules. Health is the only active pilot. A scaffold folder means a future boundary has been reserved; it does not imply data or analytical support exists.

```text
kgraph_llm/
├── cli.py
├── core/
│   └── contracts.py               # shared typed request/result contracts
├── orchestration/
│   └── pipeline.py                # question-to-graph-to-SQL-to-findings flow
├── knowledge_graph/
│   ├── networkx_repository.py     # embedded graph, traversal, JSON persistence
│   ├── definition.py              # ministry graph-definition contract
│   └── service.py                 # graph path, load, and initialization
├── llm_control/
│   ├── base.py                    # provider-neutral LLM interface
│   ├── factory.py                 # provider selection
│   └── openai_provider.py         # optional live provider
├── governance/
│   └── sql_guard.py               # deterministic SQL execution policy
├── storage/
│   ├── database.py                # bootstrap, read-only execution, audit
│   └── sql/schema.sql             # shared operational/audit schema
└── ministries/
    ├── registry.py                # the only ministry activation point
    ├── health/                    # active pilot
    │   ├── local_llm.py           # Health-only deterministic test behavior
    │   ├── synthetic.py           # Health synthetic data generator
    │   ├── graph_definition.py    # Health semantic nodes and relationships
    │   └── sql/
    │       ├── schema.sql         # Health canonical tables/views
    │       └── demo_seed.sql      # small Health fixture
    ├── education/                 # scaffold
    ├── finance/                   # scaffold
    ├── procurement/               # scaffold
    ├── law_enforcement/           # scaffold
    ├── transport/                 # scaffold
    └── welfare/                   # scaffold
```

## Dependency rules

1. Ministry modules may depend on `core` and shared platform controls.
2. Shared controls must not import ministry business logic, except the explicit provider/bootstrap factories that select registered modules.
3. A ministry owns its canonical tables, analytical views, semantic entities/metrics/relations, fixtures, and deterministic domain methods.
4. `knowledge_graph` owns NetworkX persistence/traversal mechanics, not ministry meanings.
5. `llm_control` owns provider communication and the LLM interface, not Health, Education, or Finance rules.
6. `governance` remains deterministic and provider-neutral. An LLM cannot disable or weaken its checks.
7. `ministries/registry.py` is the only activation point. Scaffold modules have no bootstrap scripts and therefore cannot alter the database.

## Adding a ministry

1. Create `ministries/<code>/` using the shape in `ministries/README.md`.
2. Define canonical tables at written natural grains and approved analytical views.
3. Define semantic entities, fields, metrics, aliases, relationships, and dataset links in `graph_definition.py`.
4. Add small deterministic fixtures and domain-specific regression tests.
5. Add applicable method contracts or bounded test methods; unsupported questions must STOP.
6. Complete privacy, purpose, data-contract, and steward review.
7. Add ordered SQLite bootstrap scripts and the graph definition to `ministries/registry.py`; change status to `active_pilot` only after the preceding checks pass.

## Future extraction boundaries

The folders intentionally match likely future services. NetworkX can later be replaced by a graph/catalog service; LLM providers can move behind an inference gateway; governance can become a policy/execution service; and ministry modules can become separately deployed data products without rewriting their public contracts.
