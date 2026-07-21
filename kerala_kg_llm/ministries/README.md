# Ministry modules

Each ministry/domain owns its canonical schema, analytical views, semantic K-Graph registrations, fixtures, and domain-specific methods. Shared infrastructure must not contain ministry business rules.

## Required shape for a new active module

```text
ministries/<code>/
├── README.md
├── __init__.py
├── graph_definition.py  # semantic entities, datasets, metrics, aliases, relations
├── local_llm.py          # optional deterministic test adapter
├── synthetic.py          # optional test-data generator
└── sql/
    ├── schema.sql        # canonical tables and approved analytics views
    └── demo_seed.sql     # small deterministic fixture
```

To activate a module, add its ordered analytical-database bootstrap scripts and graph definition to `ministries/registry.py`. Activation should occur only after schema, semantic metadata, safety tests, and domain-owner review exist.
