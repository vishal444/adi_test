# Generic semantic query engine

The runtime does not register one SQL query per user question. It composes a small semantic-plan vocabulary over ministry metadata in the K-Graph.

## Runtime contract

The LLM may fill only the following constrained plan blocks:

- `records`, `aggregate`, `data_quality`, or `graph`
- K-Graph dataset, field, dimension, and metric identifiers
- bound filters: `=`, `!=`, `>`, `>=`, `<`, `<=`, `in`, and `contains`
- ordering over declared output fields
- ordered `add`, `subtract`, `multiply`, safe `divide`, and `absolute_difference` calculations
- `none`, `endpoint_change`, `endpoint_growth_pct`, or `endpoint_ratio` transformations
- metric comparisons using `>`, `>=`, `<`, or `<=`
- threshold comparisons and semantic top-K limits
- year/quarter/month buckets; lag, lead, rolling sum, rolling average, and rolling population standard deviation
- population z-score, percentile rank, 1.5-IQR outlier flag, linear trend slope, and descriptive correlation
- missing/distinct/duplicate counts, missing percentage, minimum, maximum, and latest-value freshness summaries
- bounded K-Graph shortest paths and neighborhoods over approved edge types

It cannot submit SQL, formulas, table names outside the retrieved graph context, arbitrary functions, or join expressions.

The complete operator registry is not included in LLM requests. Providers receive only the relevant semantic graph context and the strict semantic-plan response format. The server retains the registry for validation, execution, versioning, tests, and the `operators` CLI command.

For example, the funding/output question becomes a plan shaped like:

```json
{
  "operation": "aggregate",
  "datasets": [
    "analytics_health_hospital_funding_year",
    "analytics_health_hospital_output_year"
  ],
  "dimensions": ["hospital_id", "hospital_name", "district_name"],
  "metrics": ["operating_funding", "total_output"],
  "transform": "endpoint_growth_pct",
  "comparison": {
    "left_metric": "operating_funding",
    "operator": ">",
    "right_metric": "total_output"
  },
  "start_year": 2022,
  "end_year": 2025
}
```

Plans may also form a calculation DAG. For example, composite output can be expressed without embedding SQL:

```json
{
  "metrics": ["admissions", "outpatient_visits", "surgeries"],
  "calculations": [
    {
      "name": "admissions_plus_outpatient",
      "operator": "add",
      "left": "admissions",
      "right": "outpatient_visits"
    },
    {
      "name": "reconstructed_output",
      "operator": "add",
      "left": "admissions_plus_outpatient",
      "right": "surgeries"
    }
  ]
}
```

The K-Graph—not that plan—defines the metric formulas, aggregation behavior, units, entity/time keys, valid transformations, zero-denominator policy, dataset grains, and approved join keys. The generic compiler validates these references and produces parameterized SQL.

## Verification boundary

The generic verifier checks output columns, embedded full-result counts, result ranks, declared ordering, endpoint formulas, metric-comparison predicates, comparison margins, time-bucket shapes, data-quality invariants, and graph traversal bounds. When the complete result is returned, it independently recomputes window and statistical formulas. It then creates a conservative deterministic summary.

If a row limit truncates a window/statistical result, the compiler-controlled SQL still executes, but cross-row formula recomputation is omitted and the verification diagnostics do not claim that invariant. Request a sufficiently high governed row limit when full cross-row recomputation is required.

`EXECUTION_VERIFIED` means those compiler/result invariants passed. It cannot mechanically prove that the LLM understood the natural-language request correctly. The overall assurance therefore remains `EXPLORATORY_NOT_CERTIFIED`.

## Extending coverage

New ministries normally add datasets, field roles, metrics, formulas, aliases, relationships, and safe join paths to their graph definition. They reuse the same compiler without adding question-specific SQL.

Queries outside the current operator vocabulary stop. Broader coverage should be added as reusable platform operators—such as cohorts, robust seasonal decomposition, or graph-to-relational projections—together with compiler validation and invariant tests. It should not be added as a one-question SQL template.

## Operator priorities

Implemented now:

- relational: records, projection, bound filters, approved equijoins
- aggregation: group-by and K-Graph-governed metric formulas
- arithmetic: add, subtract, multiply, safe divide, absolute difference
- time endpoints: absolute change, percentage growth, end/start ratio
- comparison/results: metric or threshold comparison, ordering, stable rank, top-K, exact full count
- time/windows: year/quarter/month bucket, lag, lead, rolling sum/average/population standard deviation
- statistics: population z-score, percentile rank, 1.5-IQR outlier flag, linear trend slope, descriptive correlation
- data quality: missing count/percentage, distinct and duplicate counts, minimum, maximum, latest-value freshness
- graph: bounded shortest path and bounded neighborhood over approved semantic edge types

Important next operators:

- time/analysis: period-over-period change, seasonal decomposition, cohort comparison, robust median deviation
- windows: rolling minimum and maximum
- data quality: cross-dataset reconciliation and contract-health propagation
- graph: connected components, centrality, and graph-path-to-relational projections

Correlation, anomaly, and graph operators can produce review signals. They must not be presented as proof of causality, failure, misconduct, or legal responsibility.
