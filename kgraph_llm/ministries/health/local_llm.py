from __future__ import annotations

import re

from ...core.contracts import GraphContext, QuestionSpec, SemanticQueryPlan
from ...llm_control.base import LLMAdapter, LLMError


class LocalHealthDemoLLM(LLMAdapter):
    """Deterministic Health intent/plan adapter for offline regression tests."""

    name = "local-health-demo"

    def interpret(self, question: str) -> QuestionSpec:
        lowered = question.lower()
        year_values = [int(value) for value in re.findall(r"\b(20\d{2})\b", question)]
        start_year = min(year_values) if year_values else 2022
        end_year = max(year_values) if year_values else 2025
        equipment_requested = any(
            term in lowered for term in ("equipment", "asset", "machine", "downtime")
        )
        hierarchy_requested = any(
            term in lowered
            for term in ("hierarchy", "referral", "severity", "care pathway")
        )
        district_distribution_requested = any(
            term in lowered
            for term in (
                "distribution",
                "pyramid",
                "per district",
                "each district",
                "population served",
            )
        )
        care_level_requested = any(
            term in lowered for term in ("care level", "hospital level", "facility level")
        )
        surveillance_requested = any(
            term in lowered
            for term in ("admission spike", "outbreak signal", "surveillance signal")
        )
        daily_admissions_requested = "daily" in lowered and "admission" in lowered
        if (
            "hospital" not in lowered
            and not equipment_requested
            and not hierarchy_requested
            and not district_distribution_requested
            and not care_level_requested
            and not surveillance_requested
            and not daily_admissions_requested
        ):
            return QuestionSpec(
                original_question=question,
                ambiguity_flags=("No supported Health entity type could be identified.",),
            )

        metrics: list[str] = []
        defaults: list[str] = []
        ambiguity_flags: list[str] = []
        if district_distribution_requested:
            metrics.append("district_referral_pyramid")
        if hierarchy_requested:
            metrics.append("referral_hierarchy")
        if care_level_requested:
            metrics.append("care_level_inventory")
        if equipment_requested:
            metrics.append("equipment_inventory")
        if surveillance_requested:
            metrics.append("surveillance_signal_inventory")
        elif daily_admissions_requested:
            metrics.append("daily_admissions")
        if "downtime" in lowered:
            metrics.append("equipment_downtime")
        if any(term in lowered for term in ("fund", "spend", "allocation")):
            metrics.append("operating_funding")
        if not (surveillance_requested or daily_admissions_requested) and any(
            term in lowered for term in ("output", "admission", "surgery", "outpatient")
        ):
            metrics.append("total_output")
            if "output" in lowered and not any(
                term in lowered for term in ("admission", "surgery", "outpatient")
            ):
                defaults.append(
                    "output=total activity (admissions + outpatient visits + surgeries)"
                )
        if not metrics:
            metrics.append("hospital_count")

        comparison = (
            "change_relative_to_output"
            if {"operating_funding", "total_output"}.issubset(metrics)
            else "equipment_status_summary"
            if "equipment_inventory" in metrics
            else "summary"
        )
        if comparison == "change_relative_to_output" and not year_values:
            defaults.append("period=2022..2025 demo data range")
        if comparison == "change_relative_to_output" and len(set(year_values)) == 1:
            ambiguity_flags.append(
                "A growth comparison requires both a start year and an end year."
            )
        return QuestionSpec(
            original_question=question,
            entity_type=(
                "SurveillanceSignal"
                if surveillance_requested
                else "District"
                if district_distribution_requested
                else "HealthcareFacilityLevel"
                if hierarchy_requested
                else "Hospital"
                if "hospital" in lowered or care_level_requested or daily_admissions_requested
                else "Equipment"
            ),
            metric_terms=tuple(metrics),
            comparison=comparison,
            start_year=start_year,
            end_year=end_year,
            defaulted_fields=tuple(defaults),
            ambiguity_flags=tuple(ambiguity_flags),
        )

    def plan_query(
        self, spec: QuestionSpec, context: GraphContext
    ) -> SemanticQueryPlan:
        """Build an offline plan from graph roles; SQL remains compiler-owned."""
        metrics = {
            row["name"]: row
            for row in context.metrics
            if row["name"] in spec.metric_terms
        }
        if not metrics:
            raise LLMError("No K-Graph metric matched the interpreted question.")
        selected_metrics = tuple(metrics)
        aggregated_metrics = tuple(
            name for name in selected_metrics if metrics[name]["aggregation"] != "none"
        )
        if aggregated_metrics and len(aggregated_metrics) < len(selected_metrics):
            selected_metrics = aggregated_metrics
            metrics = {name: metrics[name] for name in selected_metrics}
        datasets = tuple(
            dict.fromkeys(metrics[name]["dataset_name"] for name in selected_metrics)
        )
        dataset_map = {dataset.name: dataset for dataset in context.datasets}

        if (
            spec.comparison == "change_relative_to_output"
            and len(selected_metrics) >= 2
        ):
            common_fields = set.intersection(
                *(
                    {field["column_name"] for field in dataset_map[name].fields}
                    for name in datasets
                )
            )
            role_priority = ("entity_key", "label", "dimension")
            dimensions = tuple(
                field["column_name"]
                for role in role_priority
                for field in dataset_map[datasets[0]].fields
                if field["semantic_role"] == role
                and field["column_name"] in common_fields
            )
            lowered = spec.original_question.lower()
            operator = "<" if any(word in lowered for word in ("less", "lower")) else ">"
            return SemanticQueryPlan(
                operation="aggregate",
                datasets=datasets,
                dimensions=dimensions,
                metrics=selected_metrics,
                transform="endpoint_growth_pct",
                comparison={
                    "left_metric": selected_metrics[0],
                    "operator": operator,
                    "right_metric": selected_metrics[1],
                },
                order_by=(
                    {"field": "comparison_margin_pct_points", "direction": "DESC"},
                ),
                start_year=spec.start_year,
                end_year=spec.end_year,
            )

        non_aggregated = [
            name for name in selected_metrics if metrics[name]["aggregation"] == "none"
        ]
        if non_aggregated:
            dataset = metrics[non_aggregated[0]]["dataset_name"]
            fields = tuple(
                field["column_name"]
                for field in dataset_map[dataset].fields
                if field["semantic_role"] != "provenance"
            )
            ordinal_fields = [
                field["column_name"]
                for field in dataset_map[dataset].fields
                if field["semantic_role"] == "ordinal"
            ]
            key_fields = [
                field["column_name"]
                for field in dataset_map[dataset].fields
                if field["semantic_role"] == "entity_key"
            ]
            order_field = ordinal_fields[0] if ordinal_fields else key_fields[0]
            return SemanticQueryPlan(
                operation="records",
                datasets=(dataset,),
                fields=fields,
                order_by=({"field": order_field, "direction": "ASC"},),
            )

        dataset = datasets[0]
        is_count = any(
            metrics[name]["aggregation"] == "count_distinct" for name in metrics
        )
        dimensions = tuple(
            field["column_name"]
            for field in dataset_map[dataset].fields
            if field["semantic_role"] == "dimension"
            or (not is_count and field["semantic_role"] == "label")
        )
        return SemanticQueryPlan(
            operation="aggregate",
            datasets=datasets,
            dimensions=dimensions,
            metrics=selected_metrics,
            order_by=({"field": selected_metrics[0], "direction": "DESC"},),
        )
