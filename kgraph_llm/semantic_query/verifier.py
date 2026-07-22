from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Any

from ..core.contracts import SemanticQueryPlan
from .compiler import CompiledSemanticQuery


@dataclass(frozen=True)
class QueryVerification:
    findings: str
    total_rows: int
    returned_rows: int
    truncated: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)


class SemanticResultVerifier:
    """Verify generic compiler invariants and produce a result-grounded summary."""

    def verify(
        self,
        compiled: CompiledSemanticQuery,
        rows: tuple[dict[str, Any], ...],
        *,
        row_limit: int,
    ) -> QueryVerification:
        if not rows:
            return QueryVerification(
                findings=(
                    "The execution-verified semantic query returned no qualifying rows in the governed "
                    "data snapshot."
                ),
                total_rows=0,
                returned_rows=0,
                truncated=False,
                diagnostics={
                    "verification_status": "EXECUTION_VERIFIED",
                    "row_limit": row_limit,
                },
            )
        required = set(compiled.output_columns)
        totals: set[int] = set()
        for expected_rank, row in enumerate(rows, start=1):
            missing = required - row.keys()
            if missing:
                raise ValueError(f"QUERY_RESULT_INVALID: missing columns {sorted(missing)}")
            if int(row["_result_rank"]) != expected_rank:
                raise ValueError("QUERY_RESULT_INVALID: result rank is not contiguous.")
            totals.add(int(row["_total_rows"]))
        if len(totals) != 1:
            raise ValueError("QUERY_RESULT_INVALID: inconsistent total-row metadata.")
        total = totals.pop()
        if total < len(rows):
            raise ValueError("QUERY_RESULT_INVALID: impossible total-row metadata.")

        if compiled.plan.result_limit is not None and len(rows) > compiled.plan.result_limit:
            raise ValueError("QUERY_RESULT_INVALID: result exceeds semantic top-K limit.")
        if compiled.plan.calculations:
            self._verify_calculations(compiled, rows)
        complete_result = total == len(rows)
        if compiled.plan.time_bucket:
            self._verify_time_bucket(compiled, rows)
        if compiled.plan.window_calculations and complete_result:
            self._verify_windows(compiled, rows)
        if compiled.plan.statistics and complete_result:
            self._verify_statistics(compiled, rows)
        if compiled.plan.operation == "data_quality":
            self._verify_data_quality(compiled, rows)
        if compiled.plan.transform.startswith("endpoint_"):
            self._verify_endpoint_transform(compiled, rows)
        elif compiled.plan.comparison:
            self._verify_aggregate_comparison(compiled, rows)
        self._verify_order(compiled.order_by, rows)
        truncated = total > len(rows)
        coverage = (
            f"Showing the first {len(rows)} of {total} execution-verified rows."
            if truncated
            else f"All {total} execution-verified rows are shown."
        )
        findings = self._findings(compiled, rows, coverage)
        return QueryVerification(
            findings=findings,
            total_rows=total,
            returned_rows=len(rows),
            truncated=truncated,
            diagnostics={
                "verification_status": "EXECUTION_VERIFIED",
                "row_limit": row_limit,
                "compiler_version": compiled.compiler_version,
                "skipped_invariants": [
                    *(
                        ["window_formulas: result truncated"]
                        if compiled.plan.window_calculations and not complete_result
                        else []
                    ),
                    *(
                        ["statistical_formulas: result truncated"]
                        if compiled.plan.statistics and not complete_result
                        else []
                    ),
                ],
                "checked_invariants": [
                    "output_schema",
                    "row_total",
                    "contiguous_rank",
                    "declared_order",
                    *(
                        ["endpoint_transform_formula", "comparison_predicate"]
                        if compiled.plan.transform.startswith("endpoint_")
                        else []
                    ),
                    *(
                        ["aggregate_comparison_predicate"]
                        if compiled.plan.comparison
                        and not compiled.plan.transform.startswith("endpoint_")
                        else []
                    ),
                    *(["arithmetic_calculations"] if compiled.plan.calculations else []),
                    *(["time_bucket_shape"] if compiled.plan.time_bucket else []),
                    *(
                        ["window_formulas"]
                        if compiled.plan.window_calculations and complete_result
                        else []
                    ),
                    *(
                        ["statistical_formulas"]
                        if compiled.plan.statistics and complete_result
                        else []
                    ),
                    *(
                        ["data_quality_invariants"]
                        if compiled.plan.operation == "data_quality"
                        else []
                    ),
                ],
            },
        )

    def verify_graph(
        self,
        plan: SemanticQueryPlan,
        rows: tuple[dict[str, Any], ...],
        *,
        row_limit: int,
    ) -> QueryVerification:
        operator = str(plan.graph_query.get("operator", ""))
        if operator not in {"graph_path", "graph_neighborhood"}:
            raise ValueError("QUERY_RESULT_INVALID: unknown graph operator.")
        if not rows:
            return QueryVerification(
                findings="No matching path or neighborhood was found in the governed K-Graph snapshot.",
                total_rows=0,
                returned_rows=0,
                truncated=False,
                diagnostics={
                    "verification_status": "EXECUTION_VERIFIED",
                    "row_limit": row_limit,
                    "checked_invariants": ["bounded_graph_traversal", "empty_result"],
                },
            )
        required = (
            {
                "step", "source_name", "source_kind", "relation", "target_name",
                "target_kind", "description", "_total_rows", "_result_rank",
            }
            if operator == "graph_path"
            else {"node_name", "node_kind", "distance", "_total_rows", "_result_rank"}
        )
        totals: set[int] = set()
        previous_distance = 0
        for rank, row in enumerate(rows, start=1):
            missing = required - row.keys()
            if missing:
                raise ValueError(f"QUERY_RESULT_INVALID: missing graph columns {sorted(missing)}")
            if int(row["_result_rank"]) != rank:
                raise ValueError("QUERY_RESULT_INVALID: graph rank is not contiguous.")
            totals.add(int(row["_total_rows"]))
            if operator == "graph_path" and int(row["step"]) != rank:
                raise ValueError("QUERY_RESULT_INVALID: graph path steps are not contiguous.")
            if operator == "graph_neighborhood":
                distance = int(row["distance"])
                if distance < 1 or distance < previous_distance:
                    raise ValueError("QUERY_RESULT_INVALID: graph distances are not ordered.")
                previous_distance = distance
        if len(totals) != 1:
            raise ValueError("QUERY_RESULT_INVALID: inconsistent graph total metadata.")
        total = totals.pop()
        if total < len(rows):
            raise ValueError("QUERY_RESULT_INVALID: impossible graph total metadata.")
        truncated = total > len(rows)
        if operator == "graph_path":
            findings = (
                f"The governed K-Graph found a {total}-edge path from "
                f"{rows[0]['source_name']} to {rows[-1]['target_name']}."
            )
        else:
            findings = (
                f"The governed K-Graph found {total} nodes within the requested neighborhood; "
                f"{len(rows)} are shown."
            )
        return QueryVerification(
            findings=findings,
            total_rows=total,
            returned_rows=len(rows),
            truncated=truncated,
            diagnostics={
                "verification_status": "EXECUTION_VERIFIED",
                "row_limit": row_limit,
                "checked_invariants": [
                    "output_schema", "row_total", "contiguous_rank", "bounded_graph_traversal"
                ],
            },
        )

    @staticmethod
    def _verify_time_bucket(
        compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        bucket = compiled.plan.time_bucket
        name = str(bucket.get("name", "period"))
        grain = str(bucket.get("grain", ""))
        for row in rows:
            value = row[name]
            if grain == "year":
                valid = (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    or isinstance(value, str)
                    and len(value) == 4
                    and value.isdigit()
                )
            elif grain == "month":
                valid = (
                    isinstance(value, str)
                    and len(value) == 7
                    and value[4] == "-"
                    and value[:4].isdigit()
                    and value[5:].isdigit()
                    and 1 <= int(value[5:]) <= 12
                )
            elif grain == "quarter":
                valid = (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and 1 <= value % 10 <= 4
                )
            else:
                valid = False
            if not valid:
                raise ValueError("QUERY_RESULT_INVALID: time bucket shape failed.")

    def _verify_windows(
        self, compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        for window in compiled.plan.window_calculations:
            name = str(window["name"])
            input_name = str(window["input"])
            operator = str(window["operator"])
            partition_by = tuple(str(value) for value in window.get("partition_by", []))
            order_field = str(window["order_field"])
            descending = str(window.get("direction", "ASC")).upper() == "DESC"
            for group in self._partition_rows(rows, partition_by):
                order_values = [row[order_field] for row in group]
                if len(order_values) != len(set(order_values)):
                    raise ValueError(
                        "QUERY_RESULT_INVALID: window ordering is ambiguous within a partition."
                    )
                ordered = sorted(
                    group,
                    key=lambda row: (row[order_field] is not None, row[order_field]),
                    reverse=descending,
                )
                for index, row in enumerate(ordered):
                    if operator in {"lag", "lead"}:
                        offset = int(window.get("offset", 1))
                        target = index - offset if operator == "lag" else index + offset
                        expected = (
                            ordered[target][input_name]
                            if 0 <= target < len(ordered)
                            else None
                        )
                    else:
                        size = int(window.get("window", 3))
                        values = [
                            float(candidate[input_name])
                            for candidate in ordered[max(0, index - size + 1) : index + 1]
                            if candidate[input_name] is not None
                        ]
                        if not values:
                            expected = None
                        elif operator == "rolling_sum":
                            expected = sum(values)
                        elif operator == "rolling_average":
                            expected = sum(values) / len(values)
                        else:
                            mean = sum(values) / len(values)
                            expected = math.sqrt(
                                max(sum(value * value for value in values) / len(values) - mean * mean, 0)
                            )
                    self._assert_equal(row[name], expected, "window formula")

    def _verify_statistics(
        self, compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        for statistic in compiled.plan.statistics:
            operator = str(statistic["operator"])
            name = str(statistic["name"])
            partition_by = tuple(
                str(value) for value in statistic.get("partition_by", [])
            )
            for group in self._partition_rows(rows, partition_by):
                if operator == "iqr_outlier":
                    self._verify_iqr(group, statistic)
                    continue
                if operator == "correlation":
                    left = [float(row[str(statistic["left"])]) for row in group]
                    right = [float(row[str(statistic["right"])]) for row in group]
                    expected = self._correlation(left, right)
                    for row in group:
                        self._assert_equal(row[name], expected, "correlation formula")
                    continue
                input_name = str(statistic["input"])
                values = [float(row[input_name]) for row in group]
                if operator == "z_score":
                    mean = sum(values) / len(values)
                    stddev = math.sqrt(
                        max(sum(value * value for value in values) / len(values) - mean * mean, 0)
                    )
                    for row, value in zip(group, values):
                        expected = None if stddev == 0 else (value - mean) / stddev
                        self._assert_equal(row[name], expected, "z-score formula")
                elif operator == "percentile":
                    ordered_values = sorted(values)
                    first_rank = {
                        value: ordered_values.index(value) for value in set(ordered_values)
                    }
                    denominator = len(values) - 1
                    for row, value in zip(group, values):
                        expected = 0.0 if denominator == 0 else first_rank[value] / denominator
                        self._assert_equal(row[name], expected, "percentile-rank formula")
                elif operator == "trend_slope":
                    time_name = str(statistic["time"])
                    times = [float(row[time_name]) for row in group]
                    count = len(group)
                    denominator = count * sum(t * t for t in times) - sum(times) ** 2
                    expected = (
                        None
                        if denominator == 0
                        else (
                            count * sum(t * value for t, value in zip(times, values))
                            - sum(times) * sum(values)
                        )
                        / denominator
                    )
                    for row in group:
                        self._assert_equal(row[name], expected, "trend-slope formula")

    def _verify_iqr(
        self, group: tuple[dict[str, Any], ...], statistic: dict[str, Any]
    ) -> None:
        name = str(statistic["name"])
        input_name = str(statistic["input"])
        ordered = sorted(group, key=lambda row: float(row[input_name]))
        count = len(ordered)
        quotient, remainder = divmod(count, 4)
        sizes = [quotient + (1 if index < remainder else 0) for index in range(4)]
        tiles: list[list[dict[str, Any]]] = []
        cursor = 0
        for size in sizes:
            tiles.append(ordered[cursor : cursor + size])
            cursor += size
        q1 = float(tiles[0][-1][input_name]) if tiles[0] else None
        q3 = float(tiles[3][0][input_name]) if tiles[3] else None
        q1_name, q3_name = f"{name}_q1", f"{name}_q3"
        for row in group:
            self._assert_equal(row[q1_name], q1, "IQR lower quartile")
            self._assert_equal(row[q3_name], q3, "IQR upper quartile")
            expected = (
                0
                if q1 is None or q3 is None
                else int(
                    float(row[input_name]) < q1 - 1.5 * (q3 - q1)
                    or float(row[input_name]) > q3 + 1.5 * (q3 - q1)
                )
            )
            if int(row[name]) != expected:
                raise ValueError("QUERY_RESULT_INVALID: IQR outlier formula failed.")

    @staticmethod
    def _verify_data_quality(
        compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        if len(rows) != 1:
            raise ValueError("QUERY_RESULT_INVALID: data quality must return one summary row.")
        row = rows[0]
        row_count = row["row_count"]
        if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count < 0:
            raise ValueError("QUERY_RESULT_INVALID: invalid data-quality row count.")
        by_field: dict[tuple[str, str], Any] = {}
        for check in compiled.plan.data_quality_checks:
            operator = str(check["operator"])
            name = str(check["name"])
            value = row[name]
            field = str(check["field"])
            by_field[(field, operator)] = value
            if operator in {"missing_count", "distinct_count", "duplicate_count"}:
                if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= row_count:
                    raise ValueError("QUERY_RESULT_INVALID: invalid data-quality count.")
            elif operator == "missing_pct":
                if row_count == 0 and value is None:
                    continue
                if not isinstance(value, Real) or not 0 <= float(value) <= 100:
                    raise ValueError("QUERY_RESULT_INVALID: invalid missing percentage.")
        for (field, operator), value in by_field.items():
            if operator == "missing_pct" and (field, "missing_count") in by_field:
                expected = (
                    None
                    if row_count == 0
                    else 100.0 * by_field[(field, "missing_count")] / row_count
                )
                SemanticResultVerifier._assert_equal(value, expected, "missing percentage")

    @staticmethod
    def _partition_rows(
        rows: tuple[dict[str, Any], ...], partition_by: tuple[str, ...]
    ) -> tuple[tuple[dict[str, Any], ...], ...]:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            key = tuple(row[field] for field in partition_by)
            groups.setdefault(key, []).append(row)
        return tuple(tuple(group) for group in groups.values())

    @staticmethod
    def _correlation(left: list[float], right: list[float]) -> float | None:
        count = len(left)
        numerator = count * sum(a * b for a, b in zip(left, right)) - sum(left) * sum(right)
        left_term = count * sum(value * value for value in left) - sum(left) ** 2
        right_term = count * sum(value * value for value in right) - sum(right) ** 2
        denominator = math.sqrt(max(left_term * right_term, 0))
        return None if denominator == 0 else numerator / denominator

    @staticmethod
    def _assert_equal(actual: Any, expected: Any, label: str) -> None:
        if expected is None:
            if actual is not None:
                raise ValueError(f"QUERY_RESULT_INVALID: {label} failed.")
            return
        if not isinstance(actual, Real) or not math.isclose(
            float(actual), float(expected), rel_tol=1e-8, abs_tol=1e-8
        ):
            raise ValueError(f"QUERY_RESULT_INVALID: {label} failed.")

    def _verify_endpoint_transform(
        self, compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        plan = compiled.plan
        for row in rows:
            transformed: dict[str, float] = {}
            for metric in plan.metrics:
                start = row[f"{metric}_start"]
                end = row[f"{metric}_end"]
                suffix = {
                    "endpoint_change": "change",
                    "endpoint_growth_pct": "growth_pct",
                    "endpoint_ratio": "ratio",
                }[plan.transform]
                actual = row[f"{metric}_{suffix}"]
                if not all(isinstance(value, Real) for value in (start, end, actual)):
                    raise ValueError("QUERY_RESULT_INVALID: endpoint values must be numeric.")
                if plan.transform == "endpoint_growth_pct":
                    if float(start) <= 0:
                        raise ValueError(
                            "QUERY_RESULT_INVALID: endpoint denominator must be positive."
                        )
                    expected = 100.0 * (float(end) - float(start)) / float(start)
                elif plan.transform == "endpoint_ratio":
                    if float(start) == 0:
                        raise ValueError(
                            "QUERY_RESULT_INVALID: endpoint denominator must be non-zero."
                        )
                    expected = float(end) / float(start)
                else:
                    expected = float(end) - float(start)
                if not math.isclose(float(actual), expected, rel_tol=0, abs_tol=0.011):
                    raise ValueError(
                        f"QUERY_RESULT_INVALID: endpoint formula failed for metric {metric!r}."
                    )
                transformed[metric] = expected
            if plan.comparison:
                left = str(plan.comparison["left_metric"])
                right = str(plan.comparison["right_metric"])
                operator = str(plan.comparison["operator"])
                if not self._compare(transformed[left], operator, transformed[right]):
                    raise ValueError("QUERY_RESULT_INVALID: comparison predicate failed.")
                expected_margin = abs(transformed[left] - transformed[right])
                margin_name = (
                    "comparison_margin_pct_points"
                    if plan.transform == "endpoint_growth_pct"
                    else "comparison_margin"
                )
                if not math.isclose(
                    float(row[margin_name]),
                    expected_margin,
                    rel_tol=0,
                    abs_tol=0.011,
                ):
                    raise ValueError("QUERY_RESULT_INVALID: comparison margin failed.")

    def _verify_calculations(
        self, compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        for row in rows:
            values = dict(row)
            for calculation in compiled.plan.calculations:
                name = str(calculation["name"])
                operator = str(calculation["operator"])
                left = values[str(calculation["left"])]
                right = values[str(calculation["right"])]
                if not isinstance(left, Real) or not isinstance(right, Real):
                    raise ValueError("QUERY_RESULT_INVALID: arithmetic inputs must be numeric.")
                if operator == "add":
                    expected = float(left) + float(right)
                elif operator == "subtract":
                    expected = float(left) - float(right)
                elif operator == "multiply":
                    expected = float(left) * float(right)
                elif operator == "absolute_difference":
                    expected = abs(float(left) - float(right))
                elif operator == "divide":
                    expected = (
                        None
                        if float(right) == 0
                        else float(calculation.get("scale", 1.0))
                        * float(left)
                        / float(right)
                    )
                else:
                    raise ValueError("QUERY_RESULT_INVALID: unknown arithmetic operator.")
                actual = row[name]
                if expected is None:
                    if actual is not None:
                        raise ValueError("QUERY_RESULT_INVALID: division zero policy failed.")
                elif not isinstance(actual, Real) or not math.isclose(
                    float(actual), expected, rel_tol=1e-9, abs_tol=1e-9
                ):
                    raise ValueError("QUERY_RESULT_INVALID: arithmetic calculation failed.")
                values[name] = actual

    def _verify_aggregate_comparison(
        self, compiled: CompiledSemanticQuery, rows: tuple[dict[str, Any], ...]
    ) -> None:
        comparison = compiled.plan.comparison
        for row in rows:
            left_value = row[str(comparison["left"])]
            right_value = (
                row[str(comparison["right"])]
                if "right" in comparison
                else comparison["right_value"]
            )
            if not isinstance(left_value, Real) or not isinstance(right_value, Real):
                raise ValueError("QUERY_RESULT_INVALID: comparison values must be numeric.")
            left = float(left_value)
            right = float(right_value)
            if not self._compare(left, str(comparison["operator"]), right):
                raise ValueError("QUERY_RESULT_INVALID: aggregate comparison failed.")
            if not math.isclose(
                float(row["comparison_margin"]),
                abs(left - right),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                raise ValueError("QUERY_RESULT_INVALID: aggregate comparison margin failed.")

    @staticmethod
    def _compare(left: float, operator: str, right: float) -> bool:
        return {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[operator]

    @staticmethod
    def _verify_order(
        order: tuple[tuple[str, str], ...], rows: tuple[dict[str, Any], ...]
    ) -> None:
        for previous, current in zip(rows, rows[1:]):
            for field, direction in order:
                left = previous[field]
                right = current[field]
                if left == right:
                    continue
                if left is None:
                    correctly_ordered = direction == "ASC"
                elif right is None:
                    correctly_ordered = direction == "DESC"
                else:
                    correctly_ordered = left < right if direction == "ASC" else left > right
                if not correctly_ordered:
                    raise ValueError("QUERY_RESULT_INVALID: declared ordering failed.")
                break

    @staticmethod
    def _findings(
        compiled: CompiledSemanticQuery,
        rows: tuple[dict[str, Any], ...],
        coverage: str,
    ) -> str:
        plan = compiled.plan
        leader = rows[0]
        if plan.transform.startswith("endpoint_"):
            dimension_text = ", ".join(
                f"{name.replace('_', ' ')}={leader[name]}" for name in plan.dimensions[:3]
            )
            suffix, unit = {
                "endpoint_change": ("change", ""),
                "endpoint_growth_pct": ("growth_pct", "%"),
                "endpoint_ratio": ("ratio", ""),
            }[plan.transform]
            metric_text = "; ".join(
                f"{name.replace('_', ' ')} {suffix.replace('_', ' ')}="
                f"{leader[f'{name}_{suffix}']}{unit}"
                for name in plan.metrics
            )
            return (
                f"The generic semantic plan returned {len(rows)} execution-verified endpoint-comparison "
                f"rows. {coverage} The first ranked row is {dimension_text}; {metric_text}. "
                "This is a descriptive result from the governed data snapshot, not evidence of "
                "causation, waste, or wrongdoing."
            )
        visible = [
            name
            for name in compiled.output_columns
            if not name.startswith("_")
        ]
        preview = ", ".join(
            f"{name.replace('_', ' ')}={leader[name]}" for name in visible[:4]
        )
        return (
            f"The generic semantic plan returned {len(rows)} execution-verified rows. {coverage} "
            f"The first ranked row is {preview}. This summary is limited to the governed data "
            "snapshot and declared semantic plan."
        )
