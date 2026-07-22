# Architecture decisions and corrections

This implementation uses the supplied Architecture v5 as direction, with the following practical corrections.

1. The semantic K-Graph is a governed catalog, not the system of record. It describes entities, metrics, analytical frames, fields, grains, joins, and observable relationships. Measures are computed in the database.
   The pilot implements this catalog as a persisted NetworkX property graph while keeping Health facts and analytical views in SQLite.
2. The LLM does not receive unrestricted database access and cannot produce executable SQL. It first produces a `QuestionSpec`; the application retrieves a bounded semantic subgraph; then the LLM selects a constrained semantic plan using exact graph identifiers.
3. Generated SQL is not trusted merely because it parses. A deterministic gate restricts it to one read-only `SELECT`/`WITH`, approved analytical views, bound parameters, a row limit, a virtual-machine step budget, and a read-only database connection.
4. Method ambiguity is a stop state. The pilot does not silently answer an unsupported procurement, education, or cross-domain question using a superficially related table.
5. Graph relations are typed observations or semantic relations. The graph must not contain conclusions such as `suspiciously_related_to` as source-of-truth facts.
6. A successful query is labeled `EXPLORATORY_NOT_CERTIFIED`. Production certification additionally requires identity controls, authorization, active data contracts, method registration, evidence review, and human governance described in the source document.
7. Negative findings are scoped to the executed query and available snapshot. They are not claims that no real-world relationship or issue exists.
8. NetworkX provides real graph nodes, directed typed edges, and traversal behavior for this single-process pilot. It is not a multi-user graph database; persistence, transactions, access controls, and horizontal scaling must be revisited before production.

## Implemented flow

```text
user question
  -> LLM question interpretation
  -> deterministic consequence/ambiguity preflight
  -> semantic K-Graph retrieval
  -> LLM semantic plan (no SQL)
  -> deterministic plan validation
     -> relational/statistical plan: generic SQL compilation
        -> SQL allowlist + read-only central-database execution
     -> graph plan: bounded NetworkX traversal (no SQL)
  -> formula/predicate/graph-bound/order/total verification
  -> deterministic findings + provenance
  -> audit metadata
```

The default `local` adapter makes this flow reproducible without network access. The optional Google Gemini and OpenAI adapters use the same semantic-plan contract; switching providers does not bypass graph identifiers, compiler constraints, execution controls, or result verification. There is no raw LLM-SQL fallback.
