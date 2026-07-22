# Kerala Governed LLM Analytics Pilot

This repository is a runnable first slice of the architecture described in the supplied Kerala Government Governed LLM Architecture v5 document. A user asks a natural-language question; an LLM creates a canonical question specification; the application retrieves relevant entities, metrics, formulas, fields, grains, relationships, and dataset join paths from a semantic K-Graph; and the LLM selects a constrained semantic query plan. A generic compiler—not the LLM—turns that plan into SQL and a generic verifier checks its declared result invariants.

The reusable operator vocabulary covers governed records, filters, joins, aggregation, arithmetic, endpoint change/growth/ratio, time buckets, lag/lead, rolling calculations, z-score, percentile rank, IQR flags, trend slope, descriptive correlation, data-quality summaries, bounded graph paths/neighborhoods, ordering, top-K, exact counts, and stable ranking. The funding/output question is one composition of those operators; it has no question-specific SQL method. An embedded NetworkX directed property graph is the semantic K-Graph; SQLite is only the central analytical database for the pilot. The included data is synthetic demonstration data, not Kerala Government data.

Health is currently the only active ministry module. Education, Finance, Procurement, Law Enforcement, Transport, and Welfare have separate scaffold folders but contain no active schemas or semantic definitions yet.

Health also includes a deterministic once-daily admission surveillance job. Hospitals submit aggregate admissions for a closed reporting date by syndrome, age band, and patient residence district. The job checks submission completeness, compares that date with the previous eight matching weekdays, and stores hospital-, district-, and Kerala-level `WATCH` or `HIGH` signals for human review. A signal is explicitly not an outbreak declaration.

## Quick start

Requirement: Python 3.11+. NetworkX is installed with the project; no graph server, Java runtime, Docker, or credentials are needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m kgraph_llm graph-init
python3 -m kgraph_llm init --reset
python3 -m kgraph_llm query \
  "Which hospitals received more operating funding without comparable output growth?"
```

Run the daily admission-spike check for yesterday in Kerala, or supply an explicit closed reporting date:

```bash
python3 -m kgraph_llm daily-surveillance
python3 -m kgraph_llm daily-surveillance --reporting-date 2026-07-21 --json
```

The demo seed contains a date-relative respiratory-admission spike, so the first command produces reviewable example signals after a fresh `init`. Production scheduling should run this command once after the daily sector-submission cutoff.

`graph-init` compiles the active ministry graph definitions into `var/knowledge_graph.json`. Set `KGRAPH_PATH` only if a different location is required. Inspect its counts with `python3 -m kgraph_llm graph-status`.

Show active and planned ministry modules:

```bash
python3 -m kgraph_llm ministries
```

Inspect the query engine's implemented and planned operator catalogue:

```bash
python3 -m kgraph_llm operators
```

For a larger test database, load exactly 2,000 rows into each high-cardinality business table:

```bash
python3 -m kgraph_llm seed --rows-per-table 2000 --reset
```

This creates 2,000 hospitals, 2,000 funding records, 2,000 output records, and 2,000 hospital-equipment records. The two annual fact tables contain 2022 and 2025 observations for 1,000 hospitals, enabling growth comparisons. The district table contains Kerala's 14 districts. Semantic metadata and audit tables are intentionally not padded with meaningless records.

The Health module also stores a 70-row approximate district referral-pyramid profile: 14 districts multiplied by five district-level facility tiers. These are planning ranges supplied for the pilot, not verified observed Kerala facility counts. Medical colleges and disease-specific super-specialty institutes remain higher referral resources outside the assumed per-district count profile.

```bash
python3 -m kgraph_llm query \
  "Show the typical referral pyramid distribution for each Kerala district" \
  --row-limit 100
```

To inspect the complete question specification, graph context, SQL, rows, and provenance:

```bash
python3 -m kgraph_llm query \
  "Compare hospital funding and output from 2022 to 2025" --json
```

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Live LLM mode

The default `local` provider is deterministic and intended for development, demonstrations, and regression tests. Google Gemini and OpenAI perform two bounded stages: question interpretation and semantic-plan selection. They never generate executable SQL and never summarize unchecked rows. The compiler and verifier are provider-neutral.

Google Gemini:

```bash
cp .env.example .env
# Edit .env and replace the key placeholder. The CLI loads cwd/.env automatically.
python3 -m kgraph_llm query \
  "Show the equipment belonging to each hospital" \
  --provider google
```

Exported shell variables take precedence over `.env`. The adapter also accepts `GOOGLE_API_KEY` as a fallback variable. Keep keys out of source control; use a secret manager in production.

OpenAI:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-terra"  # optional
python3 -m kgraph_llm query \
  "Compare hospital funding and output from 2022 to 2025" \
  --provider openai
```

Only the question specification, relevant approved semantic metadata, and the required plan format are sent to the selected live model. Database result rows and the internal operator registry are not sent. A real government deployment must add purpose authorization and data-classification filtering before enabling an external provider.

## Safety and governance boundaries

- Only a single `SELECT` or `WITH` query is accepted.
- Only K-Graph-registered analytical views may be queried.
- NetworkX stores semantic entities, datasets, fields, metrics/formulas, aliases, typed relationships, and approved dataset join keys in a local JSON graph; it does not store Health measures.
- Values use bound parameters; result rows and SQLite VM work are capped.
- The execution connection is read-only and has an authorizer that rejects mutation and DDL.
- Unsupported or ambiguous questions stop before SQL execution.
- The LLM can emit only the semantic-plan vocabulary; unknown datasets, fields, metrics, joins, filters, transformations, and order expressions are rejected.
- Generic operators own SQL construction, endpoint formulas, predicates, stable ranking, exact qualifying-row totals, and result-grounded findings.
- Results are rejected if applicable recomputed growth, arithmetic, window/statistical formulas, comparison margins, predicates, quality invariants, graph bounds, ordering, ranks, output schema, or embedded totals do not verify.
- `EXECUTION_VERIFIED` means the plan compiled and its declared numerical/result invariants passed; it does not prove that the LLM chose the intended plan.
- Registered defaults (such as the demo period and composite output definition) are disclosed in the question specification and CLI output.
- Audit records store a hash of the raw question, question specification, semantic plan, compiler version, SQL, provider, status, row count, and verification provenance—not result payloads.
- Every successful pilot result is `PASS_WITH_LIMITATIONS` and `EXPLORATORY_NOT_CERTIFIED`.
- Daily surveillance refuses to evaluate when complete hospital submissions are below its governed threshold; generated signals remain `NEEDS_REVIEW` until an authorized public-health workflow verifies or dismisses them.

These controls reduce risk, but they do not prove that the LLM interpreted the user's intent correctly. Production should additionally use semantic-plan evaluations, clarification thresholds, warehouse-native workload controls, service identities, row/column security, policy-filtered graph projections, active data contracts, and human review for consequential findings.

## Repository map

- `kgraph_llm/orchestration/` — end-to-end governed flow.
- `kgraph_llm/knowledge_graph/` — NetworkX persistence, graph bootstrap, and subgraph retrieval control.
- `kgraph_llm/llm_control/` — provider-neutral LLM contract and live providers.
- `kgraph_llm/semantic_query/` — generic plan-to-SQL compiler and result verifier.
- `kgraph_llm/governance/` — deterministic SQL and policy gates.
- `kgraph_llm/storage/` — database bootstrap, execution, and audit control.
- `kgraph_llm/ministries/` — independently owned ministry domain modules.
- `kgraph_llm/ministries/health/` — active Health schema, semantic metadata, offline intent adapter, and synthetic data.
- `docs/project-structure.md` — dependency rules and ministry onboarding plan.
- `docs/networkx-kgraph.md` — NetworkX node/edge model and operations.
- `docs/semantic-query-engine.md` — generic plan vocabulary, compilation, verification, and extension rules.
- `docs/architecture-decisions.md` — corrections applied to the source architecture.
- `progress.md` — current status, limitations, and next milestones.

## Important claim boundary

This is an exploratory engineering pilot. It does not certify methods, infer causality, establish wrongdoing, estimate unknown graph-search recall, or authorize consequential government action. See [the architecture decisions](docs/architecture-decisions.md) and [current progress](progress.md).
