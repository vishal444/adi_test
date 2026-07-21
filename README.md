# Kerala Governed LLM Analytics Pilot

This repository is a runnable first slice of the architecture described in the supplied Kerala Government Governed LLM Architecture v5 document. A user asks a natural-language question; an LLM creates a canonical question specification; the application retrieves relevant entities, metrics, analytical frames, fields, and relations from a semantic K-Graph; the LLM proposes SQL; deterministic controls validate and execute that SQL against a read-only central analytics database; and the LLM explains the bounded result with provenance and limitations.

The pilot deliberately implements one health-domain method deeply: comparing hospital operating-funding growth with service-output growth. An embedded NetworkX directed property graph is the semantic K-Graph; SQLite is only the central analytical database for the pilot. The included data is synthetic demonstration data, not Kerala Government data.

Health is currently the only active ministry module. Education, Finance, Procurement, Law Enforcement, Transport, and Welfare have separate scaffold folders but contain no active schemas or query methods yet.

## Quick start

Requirement: Python 3.11+. NetworkX is installed with the project; no graph server, Java runtime, Docker, or credentials are needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m kerala_kg_llm graph-init
python3 -m kerala_kg_llm init --reset
python3 -m kerala_kg_llm query \
  "Which hospitals received more operating funding without comparable output growth?"
```

`graph-init` compiles the active ministry graph definitions into `var/knowledge_graph.json`. Set `KGRAPH_PATH` only if a different location is required. Inspect its counts with `python3 -m kerala_kg_llm graph-status`.

Show active and planned ministry modules:

```bash
python3 -m kerala_kg_llm ministries
```

For a larger test database, load exactly 2,000 rows into each high-cardinality business table:

```bash
python3 -m kerala_kg_llm seed --rows-per-table 2000 --reset
```

This creates 2,000 hospitals, 2,000 funding records, and 2,000 output records. The two fact tables contain 2022 and 2025 observations for 1,000 hospitals, enabling growth comparisons. The district table contains Kerala's 14 districts. Semantic metadata and audit tables are intentionally not padded with meaningless records.

To inspect the complete question specification, graph context, SQL, rows, and provenance:

```bash
python3 -m kerala_kg_llm query \
  "Compare hospital funding and output from 2022 to 2025" --json
```

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Live LLM mode

The default `local` provider is deterministic and intended for development, demonstrations, and regression tests. An optional OpenAI Responses API adapter performs all three LLM stages while retaining the same graph and SQL gates.

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-terra"  # optional
python3 -m kerala_kg_llm query \
  "Compare hospital funding and output from 2022 to 2025" \
  --provider openai
```

Only approved schema metadata and query results are sent to the selected live model. A real government deployment must add purpose authorization and data-classification filtering before enabling an external provider.

## Safety and governance boundaries

- Only a single `SELECT` or `WITH` query is accepted.
- Only K-Graph-registered analytical views may be queried.
- NetworkX stores semantic entities, datasets, fields, metrics, aliases, and typed relationships in a local JSON graph; it does not store Health measures.
- Values use bound parameters; result rows and SQLite VM work are capped.
- The execution connection is read-only and has an authorizer that rejects mutation and DDL.
- Unsupported or ambiguous questions stop before SQL execution.
- Registered defaults (such as the demo period and composite output definition) are disclosed in the question specification and CLI output.
- Audit records store a hash of the raw question, the question specification, SQL, provider, status, and row count—not result payloads.
- Every successful pilot result is `PASS_WITH_LIMITATIONS` and `EXPLORATORY_NOT_CERTIFIED`.

These controls reduce risk; they do not make arbitrary generated SQL safe for production. Production should use a real SQL parser/AST policy, warehouse-native workload controls, service identities, row/column security, policy-filtered graph projections, and approved method contracts.

## Repository map

- `kerala_kg_llm/orchestration/` — end-to-end governed flow.
- `kerala_kg_llm/knowledge_graph/` — NetworkX persistence, graph bootstrap, and subgraph retrieval control.
- `kerala_kg_llm/llm_control/` — provider-neutral LLM contract and live providers.
- `kerala_kg_llm/governance/` — deterministic SQL and policy gates.
- `kerala_kg_llm/storage/` — database bootstrap, execution, and audit control.
- `kerala_kg_llm/ministries/` — independently owned ministry domain modules.
- `kerala_kg_llm/ministries/health/` — active Health schema, semantic metadata, methods, and synthetic data.
- `docs/project-structure.md` — dependency rules and ministry onboarding plan.
- `docs/networkx-kgraph.md` — NetworkX node/edge model and operations.
- `docs/architecture-decisions.md` — corrections applied to the source architecture.
- `progress.md` — current status, limitations, and next milestones.

## Important claim boundary

This is an exploratory engineering pilot. It does not certify methods, infer causality, establish wrongdoing, estimate unknown graph-search recall, or authorize consequential government action. See [the architecture decisions](docs/architecture-decisions.md) and [current progress](progress.md).
