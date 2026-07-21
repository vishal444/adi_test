from __future__ import annotations

import re
from typing import Any

from ...core.contracts import GraphContext, QuestionSpec, SQLProposal
from ...llm_control.base import LLMAdapter, LLMError


class LocalHealthDemoLLM(LLMAdapter):
    """Deterministic Health-only adapter for offline demos and regression tests."""

    name = "local-health-demo"

    def interpret(self, question: str) -> QuestionSpec:
        lowered = question.lower()
        year_values = [int(value) for value in re.findall(r"\b(20\d{2})\b", question)]
        start_year = min(year_values) if year_values else 2022
        end_year = max(year_values) if year_values else 2025
        if "hospital" not in lowered:
            return QuestionSpec(
                original_question=question,
                ambiguity_flags=("No supported Health entity type could be identified.",),
            )

        metrics = []
        defaults = []
        ambiguity_flags = []
        if any(term in lowered for term in ("fund", "spend", "allocation")):
            metrics.append("operating_funding")
        if any(term in lowered for term in ("output", "admission", "surgery", "outpatient")):
            metrics.append("total_output")
            if "output" in lowered and not any(
                term in lowered for term in ("admission", "surgery", "outpatient")
            ):
                defaults.append("output=total activity (admissions + outpatient visits + surgeries)")
        if not metrics:
            metrics.append("hospital_count")

        comparison = "change_relative_to_output" if len(metrics) > 1 else "summary"
        if comparison == "change_relative_to_output" and not year_values:
            defaults.append("period=2022..2025 demo data range")
        if comparison == "change_relative_to_output" and len(set(year_values)) == 1:
            ambiguity_flags.append("A growth comparison requires both a start year and an end year.")
        return QuestionSpec(
            original_question=question,
            entity_type="Hospital",
            metric_terms=tuple(metrics),
            comparison=comparison,
            start_year=start_year,
            end_year=end_year,
            defaulted_fields=tuple(defaults),
            ambiguity_flags=tuple(ambiguity_flags),
        )

    def generate_sql(self, spec: QuestionSpec, context: GraphContext) -> SQLProposal:
        available = {dataset.name for dataset in context.datasets}
        if {"operating_funding", "total_output"}.issubset(spec.metric_terms):
            required = {
                "analytics_health_hospital_funding_year",
                "analytics_health_hospital_output_year",
            }
            if not required.issubset(available):
                raise LLMError("The semantic graph did not return both required Health frames.")
            sql = """
                WITH yearly AS (
                    SELECT f.hospital_id,
                           f.hospital_name,
                           f.district_name,
                           f.fiscal_year,
                           SUM(f.operating_funding) AS funding,
                           SUM(o.admissions + o.outpatient_visits + o.surgeries) AS output
                    FROM analytics_health_hospital_funding_year AS f
                    JOIN analytics_health_hospital_output_year AS o
                      ON o.hospital_id = f.hospital_id
                     AND o.fiscal_year = f.fiscal_year
                    WHERE f.fiscal_year BETWEEN ? AND ?
                    GROUP BY f.hospital_id, f.hospital_name, f.district_name, f.fiscal_year
                ),
                start_end AS (
                    SELECT hospital_id,
                           hospital_name,
                           district_name,
                           MAX(CASE WHEN fiscal_year = ? THEN funding END) AS start_funding,
                           MAX(CASE WHEN fiscal_year = ? THEN funding END) AS end_funding,
                           MAX(CASE WHEN fiscal_year = ? THEN output END) AS start_output,
                           MAX(CASE WHEN fiscal_year = ? THEN output END) AS end_output
                    FROM yearly
                    GROUP BY hospital_id, hospital_name, district_name
                )
                SELECT hospital_name,
                       district_name,
                       start_funding,
                       end_funding,
                       ROUND(100.0 * (end_funding - start_funding) / NULLIF(start_funding, 0), 2)
                           AS funding_growth_pct,
                       start_output,
                       end_output,
                       ROUND(100.0 * (end_output - start_output) / NULLIF(start_output, 0), 2)
                           AS output_growth_pct,
                       ROUND(
                           100.0 * (end_funding - start_funding) / NULLIF(start_funding, 0)
                           - 100.0 * (end_output - start_output) / NULLIF(start_output, 0),
                           2
                       ) AS growth_gap_pct_points
                FROM start_end
                WHERE start_funding IS NOT NULL AND end_funding IS NOT NULL
                  AND start_output IS NOT NULL AND end_output IS NOT NULL
                ORDER BY growth_gap_pct_points DESC
            """
            years = (spec.start_year or 2022, spec.end_year or 2025)
            return SQLProposal(
                sql=sql,
                parameters=(years[0], years[1], years[0], years[1], years[0], years[1]),
                rationale="Join equal-grain Health funding and output frames and compare growth.",
            )

        if "hospital_count" in spec.metric_terms:
            if "analytics_health_hospital_funding_year" not in available:
                raise LLMError("No governed hospital analytical frame was retrieved.")
            return SQLProposal(
                sql="""
                    SELECT district_name, COUNT(DISTINCT hospital_id) AS hospital_count
                    FROM analytics_health_hospital_funding_year
                    GROUP BY district_name
                    ORDER BY hospital_count DESC, district_name
                """,
                rationale="Count hospitals by district using the governed Health frame.",
            )
        raise LLMError("No registered Health demo method supports this metric combination.")

    def analyze(self, spec: QuestionSpec, rows: tuple[dict[str, Any], ...]) -> str:
        if not rows:
            return "No qualifying rows were returned within the approved data and query envelope."
        if "growth_gap_pct_points" in rows[0]:
            leader = rows[0]
            positive = [row for row in rows if (row.get("growth_gap_pct_points") or 0) > 0]
            return (
                f"{len(positive)} of {len(rows)} hospitals had funding growth above output growth. "
                f"The largest gap was {leader['hospital_name']} in {leader['district_name']}: "
                f"funding grew {leader['funding_growth_pct']}% while output grew "
                f"{leader['output_growth_pct']}%, a {leader['growth_gap_pct_points']} percentage-point gap. "
                "This is a descriptive signal for review, not evidence of waste or causation."
            )
        return f"The governed query returned {len(rows)} grouped result rows."

