from __future__ import annotations

from ...knowledge_graph.definition import GraphDefinition


GRAPH_DEFINITION = GraphDefinition(
    ministry="health",
    registry_version="health-pilot-2026-07-21",
    entities=(
        {"name": "Hospital", "description": "Government hospital or medical facility with stable identity."},
        {"name": "District", "description": "Effective-dated Kerala administrative district."},
        {"name": "FiscalYear", "description": "Government fiscal reporting period."},
    ),
    datasets=(
        {
            "name": "analytics_health_hospital_funding_year",
            "description": "Reviewed operating funding analytical view.",
            "grain": "Hospital x FiscalYear x FundingCategory",
            "governed": True,
            "fields": (
                {"column_name": "hospital_id", "semantic_role": "entity_key", "data_type": "integer", "description": "Stable hospital key.", "ordinal": 1},
                {"column_name": "hospital_name", "semantic_role": "label", "data_type": "text", "description": "Hospital display name.", "ordinal": 2},
                {"column_name": "district_name", "semantic_role": "dimension", "data_type": "text", "description": "District under administrative attribution.", "ordinal": 3},
                {"column_name": "fiscal_year", "semantic_role": "time", "data_type": "integer", "description": "Fiscal year start year.", "ordinal": 4},
                {"column_name": "funding_category", "semantic_role": "dimension", "data_type": "text", "description": "Funding category.", "ordinal": 5},
                {"column_name": "operating_funding", "semantic_role": "measure", "data_type": "real", "description": "Operating funding in lakh rupees.", "ordinal": 6},
                {"column_name": "source_version", "semantic_role": "provenance", "data_type": "text", "description": "Source dataset version.", "ordinal": 7},
            ),
        },
        {
            "name": "analytics_health_hospital_output_year",
            "description": "Reviewed hospital service output analytical view.",
            "grain": "Hospital x FiscalYear",
            "governed": True,
            "fields": (
                {"column_name": "hospital_id", "semantic_role": "entity_key", "data_type": "integer", "description": "Stable hospital key.", "ordinal": 1},
                {"column_name": "hospital_name", "semantic_role": "label", "data_type": "text", "description": "Hospital display name.", "ordinal": 2},
                {"column_name": "district_name", "semantic_role": "dimension", "data_type": "text", "description": "District under administrative attribution.", "ordinal": 3},
                {"column_name": "fiscal_year", "semantic_role": "time", "data_type": "integer", "description": "Fiscal year start year.", "ordinal": 4},
                {"column_name": "admissions", "semantic_role": "measure", "data_type": "integer", "description": "Annual admissions.", "ordinal": 5},
                {"column_name": "outpatient_visits", "semantic_role": "measure", "data_type": "integer", "description": "Annual outpatient visits.", "ordinal": 6},
                {"column_name": "surgeries", "semantic_role": "measure", "data_type": "integer", "description": "Annual surgeries.", "ordinal": 7},
                {"column_name": "source_version", "semantic_role": "provenance", "data_type": "text", "description": "Source dataset version.", "ordinal": 8},
            ),
        },
    ),
    metrics=(
        {"name": "operating_funding", "dataset_name": "analytics_health_hospital_funding_year", "expression": "SUM(operating_funding)", "aggregation": "sum", "description": "Operating funding in lakh rupees."},
        {"name": "total_output", "dataset_name": "analytics_health_hospital_output_year", "expression": "SUM(admissions + outpatient_visits + surgeries)", "aggregation": "sum", "description": "Composite activity count for this pilot; components remain visible."},
        {"name": "hospital_count", "dataset_name": "analytics_health_hospital_funding_year", "expression": "COUNT(DISTINCT hospital_id)", "aggregation": "count_distinct", "description": "Distinct hospital count."},
    ),
    relationships=(
        {"from_entity": "Hospital", "predicate": "located_in", "to_entity": "District", "join_expression": "hospital.district_id = district.district_id", "description": "Administrative location, not service catchment."},
        {"from_entity": "Hospital", "predicate": "has_funding_in", "to_entity": "FiscalYear", "join_expression": "hospital_funding.hospital_id = hospital.hospital_id", "description": "Observed funding by fiscal year."},
        {"from_entity": "Hospital", "predicate": "reports_output_in", "to_entity": "FiscalYear", "join_expression": "hospital_output.hospital_id = hospital.hospital_id", "description": "Observed service activity by fiscal year."},
    ),
    aliases=(
        {"term": "hospital", "target_type": "entity", "target_name": "Hospital"},
        {"term": "hospitals", "target_type": "entity", "target_name": "Hospital"},
        {"term": "district", "target_type": "entity", "target_name": "District"},
        {"term": "funding", "target_type": "metric", "target_name": "operating_funding"},
        {"term": "fund", "target_type": "metric", "target_name": "operating_funding"},
        {"term": "spend", "target_type": "metric", "target_name": "operating_funding"},
        {"term": "output", "target_type": "metric", "target_name": "total_output"},
        {"term": "admissions", "target_type": "metric", "target_name": "total_output"},
        {"term": "surgeries", "target_type": "metric", "target_name": "total_output"},
        {"term": "outpatient", "target_type": "metric", "target_name": "total_output"},
        {"term": "count", "target_type": "metric", "target_name": "hospital_count"},
    ),
    dataset_links=(
        {"dataset_name": "analytics_health_hospital_funding_year", "entity_name": "Hospital", "metric_name": "operating_funding"},
        {"dataset_name": "analytics_health_hospital_funding_year", "entity_name": "Hospital", "metric_name": "hospital_count"},
        {"dataset_name": "analytics_health_hospital_output_year", "entity_name": "Hospital", "metric_name": "total_output"},
    ),
)

