# Health

Status: `active_pilot`

Implements hospital identity, district attribution, Kerala's seven-level public healthcare referral hierarchy, an approximate five-level district referral-pyramid profile for all 14 districts, effective-dated hospital care-level classification, operating funding, service output, hospital equipment inventory/status, governed analytical views, semantic K-Graph registration, deterministic Health test behavior, and bulk synthetic data generation.

The module also implements once-daily aggregate admission surveillance. `DailyAdmissionSurveillance` evaluates one closed reporting date only after the configured hospital-submission completeness threshold passes. It uses the previous eight observations for the matching weekday, evaluates hospital, patient-residence district, and statewide counts, and stores versioned evidence with every `WATCH` or `HIGH` signal. Signals always enter `NEEDS_REVIEW`; the detector never declares an outbreak.

Health supplies data meaning—not query-specific SQL—to the shared semantic engine. `graph_definition.py` registers metrics, formulas, field roles, grains, aliases, relationships, and the approved funding/output dataset join. The generic compiler can compose these definitions for record, aggregation, filtering, ordering, and endpoint-comparison questions.

The ministry redesign adds canonical `master_*`, `analytics_*`, `finance_*`,
`restricted_*`, and `semantic_*` layers without removing the pilot fixtures.
It uses one common facility identity across modern medicine and AYUSH, keeps
monthly measurements relational, and expands the peripheral K-Graph with
organisations, facilities, categories, programmes, schemes, suppliers,
projects, metrics, capabilities, and governed dataset joins. See
[`docs/health-ministry-data-model.md`](../../../docs/health-ministry-data-model.md)
for the table inventory, grains, graph boundary, and migration guidance.

The complete current-state module reference, including database diagrams,
table grains, governed views, K-Graph topology, relational-to-graph mappings,
approved joins, query execution, and the compatibility migration path, is in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

The CLI `seed --rows-per-table 2000` workflow now populates every application
table and ensures every column has sample data. High-cardinality health,
finance, restricted-token, and surveillance tables receive exactly the
requested count; natural reference catalogs retain their governed cardinality.
