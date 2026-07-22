# Project progress

Last updated: 2026-07-22

## Current status

Milestone 1, a runnable health-domain vertical slice, is complete. The project can accept varied Health questions, canonicalize them, retrieve relevant semantic K-Graph metadata, ask an LLM for a constrained non-SQL plan, compile that plan through reusable operators, execute governed SQL, verify declared result invariants, and produce deterministic findings with provenance and an explicit exploratory assurance label.

The codebase has been reorganized for multi-ministry growth. Health is the only active module; Education, Finance, Procurement, Law Enforcement, Transport, and Welfare are explicit inactive scaffolds.

NetworkX is now the semantic K-Graph backend. The graph runs inside the Python process and persists to a local JSON file, so the complete pilot works without a graph server, Docker, Java, or credentials.

## Completed

- Reviewed the 35-page Architecture v5 document and extracted its implementation-critical boundaries.
- Created the canonical `QuestionSpec`, graph context, SQL proposal, and query outcome contracts.
- Implemented semantic entities, aliases, metrics, analytical datasets, fields, grains, and typed relationships.
- Added synthetic hospital funding and output facts plus governed analytical views.
- Added hospital equipment inventory, operational status, maintenance/downtime fields, a governed analytical view, and the `Hospital -> Equipment` semantic relationship.
- Added Kerala's seven-level Health referral hierarchy, care-level roles/access modes, effective-dated hospital classifications, severity-escalation edges, and the disease-specific super-specialty boundary.
- Added an explicitly approximate typical-medium-district referral-pyramid profile for all 14 Kerala districts, including count ranges and population/service coverage bases.
- Implemented deterministic K-Graph retrieval before SQL generation.
- Replaced the scenario-specific funding/output method with a ministry-neutral semantic query compiler.
- Added composable records, filter, aggregate, order, endpoint-growth, metric-comparison, exact-count, and stable-ranking operators.
- Added a versioned internal operator capability registry exposed through the `operators` CLI command, but not sent to LLM providers.
- Added composable add, subtract, multiply, safe divide, absolute-difference, endpoint-change, endpoint-ratio, threshold, and top-K operators.
- Added ordered arithmetic calculation stages with unit compatibility checks and deterministic recalculation in the verifier.
- Added granular admissions, outpatient-visits, and surgeries metrics so the engine can compose ratios and reconstructed totals.
- Added K-Graph dataset join paths so the compiler can join metrics without an LLM inventing join SQL.
- Added post-query verification that checks output schema, totals, ranks, ordering, and applicable endpoint formulas/comparison predicates.
- Added generic year/quarter/month time buckets, lag/lead, rolling sum/average/population-standard-deviation windows, and complete-result formula recomputation.
- Added population z-score, percentile rank, 1.5-IQR outlier flags, linear trend slope, and descriptive correlation with independent complete-result recomputation.
- Added generic missingness, distinct/duplicate count, minimum/maximum, and latest-value freshness data-quality summaries with invariant checks.
- Added bounded NetworkX shortest-path and neighborhood plans over approved edge types; these execute directly against the semantic K-Graph without SQL.
- Added exact qualifying-row and truncation reporting; the 2,000-row fixture currently returns the first 100 of 647 qualifying hospitals.
- Removed SQL generation and result-analysis functions from every LLM adapter. Providers now perform only interpretation and semantic-plan selection.
- Added offline and optional OpenAI Responses API LLM adapters.
- Added one-statement/read-only SQL validation, dataset allowlisting, parameter binding, query-plan preflight, row limits, VM-step limits, and a read-only SQLite authorizer.
- Added result analysis, provenance, stop states, and privacy-minimized execution audit metadata.
- Added explicit default disclosure and runtime read isolation for approved analytical objects.
- Added a deterministic bulk generator for 2,000-row business-table test datasets.
- Separated core contracts, orchestration, knowledge-graph control, LLM control, governance, and storage into dedicated packages.
- Moved Health schema, semantic registrations, local test logic, and synthetic data into `ministries/health`.
- Added a centralized ministry registry and independent scaffold folders for six planned domains.
- Documented dependency rules and the activation checklist for future ministries.
- Replaced the SQLite semantic registry with a persisted NetworkX property graph and versioned ministry graph definitions.
- Added deterministic graph compilation, JSON persistence, graph status/bootstrap commands, and relationship traversal tests.
- Removed semantic K-Graph tables from the SQLite analytical database.
- Added end-to-end, graph retrieval, stop-state, SQL-rejection, and read-only tests.
- Documented architecture corrections, setup, operation, claim limits, and production gaps.

## In scope and working

- Hospital operating-funding versus composite-output growth for 2022–2025 or an explicitly requested year range present in the demo data.
- Hospital counts by district through the deterministic local adapter.
- Live-model interpretation and constrained semantic planning through Google Gemini or OpenAI, followed by generic deterministic compilation and verification.

## Not yet implemented

- Procurement/finance and additional ministry schemas, data, methods, and regression fixtures.
- Higher-level seasonal decomposition, period-over-period change, robust median-deviation scoring, cohort comparison, connected components/centrality, and graph-path-to-relational projections.
- An operational entity graph for real-world nodes/edges and governed graph-search policies; current NetworkX use is the semantic K-Graph only.
- Identity tokenization, purpose authorization, row/column security, policy-specific graph projections, and export controls.
- Effective-dated reference-data workflows beyond the minimal hospital record.
- Data-contract health states, lineage impact propagation, semantic-plan confidence/clarification policy, and human attestation UI.
- A production SQL AST validator and warehouse-specific resource governor.
- API service, web UI, authentication, deployment manifests, telemetry, and operational runbooks.
- Model evaluations for question interpretation, SQL correctness, result-grounded findings, and adversarial prompt resistance.

The current annual demo fixture has only four periods (2022–2025) per small-fixture hospital and two endpoint periods per bulk-fixture hospital. The new primitives work, but this data is not sufficient for credible seasonal anomaly analysis; that requires monthly or quarterly governed facts across multiple cycles.

## Recommended next milestones

1. Replace synthetic health fixtures with a de-identified, steward-approved sample and reconciliation controls.
2. Add an explicit data-contract registry and semantic-plan evaluation/clarification gate for a certified execution lane.
3. Add a procurement/finance slice and operational entity-graph projection for approved vendor relations.
4. Move SQL validation to an AST-based policy and execute through a warehouse service identity with native quotas.
5. Build evaluation suites and a human clarification/attestation workflow before any consequential use.

## Definition of production ready

Production readiness requires more than successful SQL. A domain is ready only after source reconciliation, documented grain, governed identities/reference mappings, healthy data contracts, versioned methods, lineage, policy authorization, security review, representative model evaluations, operational monitoring, and accountable human approval are all in place.
