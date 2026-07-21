# Project progress

Last updated: 2026-07-21

## Current status

Milestone 1, a runnable health-domain vertical slice, is complete. The project can accept a hospital funding/output question, canonicalize it, retrieve relevant semantic K-Graph context and relations, generate a bounded SQL query, validate and execute it on synthetic analytical data, and produce findings with provenance and an explicit exploratory assurance label.

The codebase has been reorganized for multi-ministry growth. Health is the only active module; Education, Finance, Procurement, Law Enforcement, Transport, and Welfare are explicit inactive scaffolds.

NetworkX is now the semantic K-Graph backend. The graph runs inside the Python process and persists to a local JSON file, so the complete pilot works without a graph server, Docker, Java, or credentials.

## Completed

- Reviewed the 35-page Architecture v5 document and extracted its implementation-critical boundaries.
- Created the canonical `QuestionSpec`, graph context, SQL proposal, and query outcome contracts.
- Implemented semantic entities, aliases, metrics, analytical datasets, fields, grains, and typed relationships.
- Added synthetic hospital funding and output facts plus governed analytical views.
- Implemented deterministic K-Graph retrieval before SQL generation.
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
- Live-model interpretation/SQL/findings when `OPENAI_API_KEY` is configured.

## Not yet implemented

- Procurement/finance and additional ministry schemas, data, methods, and regression fixtures.
- An operational entity graph for real-world nodes/edges and governed graph-search policies; current NetworkX use is the semantic K-Graph only.
- Identity tokenization, purpose authorization, row/column security, policy-specific graph projections, and export controls.
- Effective-dated reference-data workflows beyond the minimal hospital record.
- Data-contract health states, lineage impact propagation, method registry/routing, and human attestation UI.
- A production SQL AST validator and warehouse-specific resource governor.
- API service, web UI, authentication, deployment manifests, telemetry, and operational runbooks.
- Model evaluations for question interpretation, SQL correctness, result-grounded findings, and adversarial prompt resistance.

## Recommended next milestones

1. Replace synthetic health fixtures with a de-identified, steward-approved sample and reconciliation controls.
2. Add explicit method-contract and data-contract registries; prevent execution unless both are active.
3. Add a procurement/finance slice and operational entity-graph projection for approved vendor relations.
4. Move SQL validation to an AST-based policy and execute through a warehouse service identity with native quotas.
5. Build evaluation suites and a human clarification/attestation workflow before any consequential use.

## Definition of production ready

Production readiness requires more than successful SQL. A domain is ready only after source reconciliation, documented grain, governed identities/reference mappings, healthy data contracts, versioned methods, lineage, policy authorization, security review, representative model evaluations, operational monitoring, and accountable human approval are all in place.
