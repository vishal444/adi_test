# Kerala health ministry analytics data model

Status: implementation baseline  
Registry version: `health-ministry-analytics-2026-07-23.3`

## Scope

This model implements the facility-centred, category-based ministry analytics
architecture described in *Kerala Health Department Analytics Platform -
Simplified Database and Peripheral Knowledge-Graph Plan*.

Operational systems continue to own patient encounters, prescriptions,
medicine batches, equipment assets, employees, purchase orders, and financial
transactions. The ministry database receives validated aggregates plus source
lineage. Daily aggregate admission surveillance remains a separate governed
path because outbreaks cannot wait for a monthly reporting cycle.

SQLite has no PostgreSQL-style schemas. The logical namespaces in the design
are therefore represented by prefixes:

| Logical layer | SQLite prefix | Purpose |
|---|---|---|
| `master` | `master_` | Shared identities, hierarchies, categories, and source systems |
| `analytics` | `analytics_` | Monthly or annual aggregate facts |
| `finance` | `finance_` | Budget, expenditure, and liability facts |
| `restricted` | `restricted_` | Tokenized beneficiary, claim, and investigation links |
| `semantic` | `semantic_` | Metric, dimension, join, quality, capability, and access rules |

The schema source of truth is
`kgraph_llm/ministries/health/sql/ministry_analytics_schema.sql`. A small,
referentially complete demonstration dataset lives in
`kgraph_llm/ministries/health/sql/ministry_analytics_seed.sql`.

## Canonical master data

`master_facility` is the common facility identity for modern medicine, AYUSH,
teaching institutions, specialty institutes, government providers, and
participating non-government providers. A facility links to:

- an effective-dated organisation;
- a governed facility type and level;
- a district and optional local body;
- a system of medicine;
- ownership, teaching, bed-capacity, and operating classifications;
- the source system and source version that supplied the identity.

Separate category dimensions govern cost, staff, equipment, service,
infrastructure, procurement, vehicles, quality, and aggregate demographic
groups. Category codes are stable; display names can evolve without rewriting
facts.

## Fact grains

| Fact | Enforced grain |
|---|---|
| `analytics_facility_monthly_summary` | Facility x Month |
| `analytics_medicine_monthly` | Facility x Month |
| `analytics_equipment_monthly` | Facility x Equipment Category x Month |
| `analytics_staffing_monthly` | Facility x Staff Category x Month |
| `analytics_service_monthly` | Facility x Service Category x Demographic Group x Month |
| `analytics_referral_flow_monthly` | Source Facility x Destination Facility x Service Category x Month |
| `analytics_procurement_monthly` | Organisation x Facility x Supplier x Procurement Category x Month |
| `analytics_supplier_performance_monthly` | Supplier x Procurement Category x Month |
| `analytics_infrastructure_monthly` | Facility x Infrastructure Category x Month |
| `analytics_vehicle_monthly` | Facility x Station x Vehicle Category x Month |
| `analytics_programme_monthly` | Programme x District x Demographic Group x Month |
| `analytics_scheme_monthly` | Scheme x District x Demographic Group x Month |
| `analytics_medical_college_annual` | Teaching Institution x Academic Year |
| `analytics_quality_monthly` | Facility x Quality Category x Month |
| `analytics_project_monthly` | Project x Month |
| `analytics_data_quality_monthly` | Source System x Organisation x Month |
| `finance_budget_monthly` | Organisation x Facility x Budget Head x Month |
| `finance_expenditure_monthly` | Facility x Cost Category x Month |
| `finance_liability_monthly` | Organisation x Facility x Cost Category x Month |

Primary keys enforce each grain. Foreign keys enforce governed dimensions.
Non-negative counts and amounts, bounded percentages, enumerated statuses, and
effective-date checks reject structurally invalid records.

Cross-table triggers additionally require facility district keys to identify
`DISTRICT` rows, local-body keys to identify direct children of the same
district, and teaching facilities to use teaching-capable facility types.
Organisation type and administrative level are controlled vocabularies used
to distinguish `OVERSEES` and `CONTROLS` semantics from mere tree depth.

## Governed views and metrics

Raw facts store metric components, not duplicate derived percentages. Governed
views calculate ratios with explicit zero-denominator handling. Examples:

- bed occupancy uses occupied bed-days / available bed-days;
- medicine sufficiency uses available / estimated-required stock value;
- equipment functionality uses functional / available equipment;
- staff sufficiency uses actually-available / required staff;
- budget utilisation uses actual expenditure / available funds;
- programme coverage uses reached / eligible population.

This fixes three ambiguities in the source plan: patient-visit denominators are
explicit, equipment procurement value exists for the maintenance-cost ratio,
and derived rates have one semantic source of truth.

The semantic registry records metric ownership, version, privacy class,
minimum data-quality score, capability inputs, allowed joins, quality rules,
and purpose-limited access policies. Joins from a facility-month dataset to a
category-grain dataset are declared one-to-many so a compiler cannot silently
multiply facility totals.

The detailed join registry is intentionally narrow: extra
category/station/demographic dimensions require governed pre-aggregation,
while programme and scheme facts are district-month rather than
facility-month facts. Department-wide cross-domain questions use
`analytics_health_department_monthly`, which attributes each record through
the organisation hierarchy and independently pre-aggregates every domain to
Department x Month before combining them. It covers activity, medicines,
equipment, staffing, services, infrastructure, vehicles, procurement, budget,
programmes, schemes, quality, projects, expenditure, liabilities, audit, data
quality and mapped surveillance signals without fact fan-out. Access-policy
role names refer to the external deployment IAM; the analytical database does
not own a duplicate role directory.

Attribution failures are not discarded. Facts whose organisation chain does
not reach a `DEPARTMENT`, plus surveillance signals without a reconciled
hospital-to-facility path, roll into `department_id = -1` (`UNASSIGNED`).
`semantic_health_department_attribution_issue` identifies unresolved
organisations, facilities and compatibility hospitals. This diagnostic and the
`UNASSIGNED` row must be reviewed before department-wide output is certified.

## Peripheral K-Graph

`kgraph_llm/ministries/health/ministry_graph.py` extends the embedded NetworkX
graph with structure and analytical meaning:

```text
Department -> Directorate -> Organisation -> Facility
                                      |          |-- FacilityType
                                      |          |-- SystemOfMedicine
                                      |          |-- ServiceCategory
                                      |          |-- StaffCategory
                                      |          |-- EquipmentCategory
                                      |          |-- InfrastructureCategory
                                      |          `-- District / LocalBody
                                      |-- Programme -> District / DemographicGroup
                                      `-- Scheme

Supplier -> ProcurementCategory
Project  -> Facility / BudgetHead
AnalyticalCapability -> AnalyticalMetric -> governed relational dataset
SourceSystem -> analytical lineage
```

The graph does not contain monthly measurements, prescriptions, medicine
batches, equipment assets, employees, patient visits, transactions, ambulance
trips, welfare payments, or person nodes. Tokenized beneficiary links remain in
the restricted relational layer and are not registered as general graph
entities or governed datasets.

## Compatibility

The earlier hospital funding/output pilot, equipment-asset demonstration,
seven-level referral hierarchy, and daily surveillance tables remain
available. They are compatibility fixtures while integrations migrate to the
common facility model. `hospital.master_facility_id` is a nullable, unique
foreign-key bridge for reconciled identities, and `Hospital IS_A Facility` is
explicit in the K-Graph. Compatibility hospital identities mutate in place;
effective-dated history belongs to the canonical facility and classification
tables. A partial unique index allows only one current classification.

New integrations should write only to the canonical prefixed model. A future
migration can replace the compatibility tables after all callers and fixtures
use `master_facility` identifiers.

## Production work still required

The schema is an implementation baseline, not a claim that source integration
is complete. Production deployment still requires:

- authoritative organisation and facility master-data reconciliation;
- signed source-to-target mappings for eHealth, KMSCL, SPARK, finance, NHM,
  SHA, AYUSH, regulatory, audit, and project systems;
- metric-owner approval for required-resource norms and outcome indicators;
- database-level roles or separate physical stores for the restricted layer;
- encryption, retention enforcement, audit logging, small-cell suppression,
  and incident-response controls;
- item-level governed drill-down for critical medicines and equipment;
- conformance tests for source freshness, late revisions, and period closure.
