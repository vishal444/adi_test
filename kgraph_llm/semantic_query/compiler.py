from __future__ import annotations

import re
from dataclasses import dataclass
from numbers import Real
from typing import Any

from ..core import GraphContext, QuestionSpec, SQLProposal, SemanticQueryPlan


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EXPRESSION = re.compile(r"^[A-Za-z0-9_(),+*/.\s-]+$")
_WORDS = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_SQL_WORDS = {"SUM", "COUNT", "DISTINCT", "AVG", "MIN", "MAX", "NULLIF"}
_FILTER_OPERATORS = {
    "=",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "in",
    "contains",
    "between",
    "is_null",
    "is_not_null",
}
_COMPARISON_OPERATORS = {">", ">=", "<", "<="}
_ARITHMETIC_OPERATORS = {"add", "subtract", "multiply", "divide", "absolute_difference"}
_WINDOW_OPERATORS = {"lag", "lead", "rolling_sum", "rolling_average", "rolling_stddev"}
_STATISTIC_OPERATORS = {
    "z_score",
    "percentile",
    "iqr_outlier",
    "trend_slope",
    "correlation",
}
_DATA_QUALITY_OPERATORS = {
    "missing_count",
    "missing_pct",
    "distinct_count",
    "duplicate_count",
    "minimum",
    "maximum",
    "freshness_max",
}


@dataclass(frozen=True)
class CompiledSemanticQuery:
    proposal: SQLProposal
    plan: SemanticQueryPlan
    output_columns: tuple[str, ...]
    order_by: tuple[tuple[str, str], ...]
    compiler_version: str = "semantic-sql-1.2.0"


class SemanticQueryCompiler:
    """Compile a constrained semantic plan using only K-Graph-approved metadata."""

    def compile(
        self,
        plan: SemanticQueryPlan,
        context: GraphContext,
        question_spec: QuestionSpec | None = None,
    ) -> CompiledSemanticQuery:
        catalog = _Catalog(context)
        if plan.operation not in {"records", "aggregate", "data_quality"}:
            raise ValueError(f"PLAN_INVALID: unsupported operation {plan.operation!r}.")
        if plan.transform not in {
            "none",
            "endpoint_change",
            "endpoint_growth_pct",
            "endpoint_ratio",
        }:
            raise ValueError(f"PLAN_INVALID: unsupported transform {plan.transform!r}.")
        if plan.transform.startswith("endpoint_") and question_spec is not None:
            if (
                question_spec.start_year is not None
                and plan.start_year != question_spec.start_year
            ) or (
                question_spec.end_year is not None
                and plan.end_year != question_spec.end_year
            ):
                raise ValueError(
                    "PLAN_INVALID: planned endpoint years differ from interpreted years."
                )
        if plan.result_limit is not None and (
            not isinstance(plan.result_limit, int)
            or isinstance(plan.result_limit, bool)
            or not 1 <= plan.result_limit <= 10_000
        ):
            raise ValueError("PLAN_INVALID: result_limit must be between 1 and 10000.")

        datasets = self._resolve_datasets(plan, catalog)
        for metric_name in plan.metrics:
            metric = catalog.metric(metric_name)
            valid_transforms = {
                value.strip()
                for value in metric.get("valid_transforms", "none").split(",")
            }
            if plan.transform not in valid_transforms:
                raise ValueError(
                    f"PLAN_INVALID: transform {plan.transform!r} is not registered for "
                    f"metric {metric_name!r}."
                )
        if plan.operation == "data_quality":
            return self._compile_data_quality(plan, catalog, datasets)
        if plan.operation == "records":
            if plan.transform != "none":
                raise ValueError("PLAN_INVALID: record queries cannot apply metric transforms.")
            if plan.calculations:
                raise ValueError("PLAN_INVALID: record calculations require aggregate mode.")
            if plan.window_calculations or plan.statistics or plan.time_bucket:
                raise ValueError("PLAN_INVALID: analytical operators require aggregate mode.")
            return self._compile_records(plan, catalog, datasets)
        if plan.data_quality_checks or plan.graph_query:
            raise ValueError("PLAN_INVALID: aggregate plan contains incompatible operators.")
        if not plan.metrics:
            raise ValueError("PLAN_INVALID: aggregate queries require at least one metric.")
        if any(catalog.metric(name)["aggregation"] == "none" for name in plan.metrics):
            raise ValueError("PLAN_INVALID: non-aggregated inventory metrics require records.")
        if plan.transform.startswith("endpoint_"):
            if plan.time_bucket or plan.window_calculations or plan.statistics:
                raise ValueError(
                    "PLAN_INVALID: endpoint transforms cannot be combined with analytical windows."
                )
            return self._compile_endpoint_growth(plan, catalog, datasets)
        return self._compile_aggregate(plan, catalog, datasets)

    def _compile_data_quality(
        self,
        plan: SemanticQueryPlan,
        catalog: _Catalog,
        datasets: tuple[str, ...],
    ) -> CompiledSemanticQuery:
        if len(datasets) != 1:
            raise ValueError("PLAN_INVALID: data quality requires exactly one dataset.")
        if plan.transform != "none" or plan.metrics or plan.calculations:
            raise ValueError("PLAN_INVALID: data quality cannot use metric transformations.")
        if plan.dimensions or plan.fields or plan.window_calculations or plan.statistics:
            raise ValueError("PLAN_INVALID: data quality cannot use analytical projections.")
        if plan.time_bucket or plan.graph_query or plan.comparison:
            raise ValueError("PLAN_INVALID: data quality contains incompatible plan fields.")
        if not plan.data_quality_checks:
            raise ValueError("PLAN_INVALID: data quality requires at least one check.")

        dataset = datasets[0]
        alias = "d0"
        available_names = {"row_count"}
        expressions = ["COUNT(*) AS row_count"]
        output = ["row_count"]
        for check in plan.data_quality_checks:
            operator = str(check.get("operator", ""))
            name = self._field_name(str(check.get("name", "")))
            field = self._field_name(str(check.get("field", "")))
            if operator not in _DATA_QUALITY_OPERATORS:
                raise ValueError(f"PLAN_INVALID: data-quality operator {operator!r} is not allowed.")
            if name in available_names:
                raise ValueError(f"PLAN_INVALID: duplicate data-quality name {name!r}.")
            catalog.field_owner(field, datasets)
            detail = catalog.field_detail(dataset, field)
            if operator == "freshness_max" and detail["semantic_role"] != "time":
                raise ValueError(
                    "PLAN_INVALID: freshness_max requires a K-Graph time-role field."
                )
            column = f"{alias}.{field}"
            expression = {
                "missing_count": f"COALESCE(SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END), 0)",
                "missing_pct": (
                    f"100.0 * COALESCE(SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END), 0) "
                    "/ NULLIF(COUNT(*), 0)"
                ),
                "distinct_count": f"COUNT(DISTINCT {column})",
                "duplicate_count": f"COUNT({column}) - COUNT(DISTINCT {column})",
                "minimum": f"MIN({column})",
                "maximum": f"MAX({column})",
                "freshness_max": f"MAX({column})",
            }[operator]
            expressions.append(f"{expression} AS {name}")
            output.append(name)
            available_names.add(name)

        where, parameters = self._filters(
            plan.filters, catalog, datasets, {dataset: alias}
        )
        order = self._normalize_order(plan.order_by, available_names)
        if not order:
            order = (("row_count", "DESC"),)
        window_order = self._order_sql(order)
        limit_clause, limit_parameters = self._limit(plan)
        sql = f"""
            WITH quality AS (
                SELECT {', '.join(expressions)}
                FROM {dataset} AS {alias}
                WHERE {where}
            ),
            ranked AS (
                SELECT quality.*,
                       COUNT(*) OVER () AS _total_rows,
                       ROW_NUMBER() OVER (ORDER BY {window_order}) AS _result_rank
                FROM quality
                WHERE 1 = 1
            )
            SELECT {', '.join(output)}, _total_rows, _result_rank
            FROM ranked
            ORDER BY _result_rank{limit_clause}
        """
        return CompiledSemanticQuery(
            SQLProposal(
                sql,
                (*parameters, *limit_parameters),
                "Generic data-quality operators compiled from K-Graph fields.",
            ),
            plan,
            (*output, "_total_rows", "_result_rank"),
            order,
        )

    @staticmethod
    def _resolve_datasets(
        plan: SemanticQueryPlan, catalog: _Catalog
    ) -> tuple[str, ...]:
        inferred = tuple(
            dict.fromkeys(catalog.metric(name)["dataset_name"] for name in plan.metrics)
        )
        datasets = plan.datasets or inferred
        if not datasets:
            raise ValueError("PLAN_INVALID: no dataset was selected.")
        unknown = set(datasets) - catalog.dataset_names
        if unknown:
            raise ValueError(f"PLAN_INVALID: datasets are absent from graph context: {sorted(unknown)}")
        if not set(inferred).issubset(datasets):
            raise ValueError("PLAN_INVALID: selected datasets do not contain every requested metric.")
        return tuple(datasets)

    def _compile_records(
        self,
        plan: SemanticQueryPlan,
        catalog: _Catalog,
        datasets: tuple[str, ...],
    ) -> CompiledSemanticQuery:
        if len(datasets) != 1:
            raise ValueError("PLAN_INVALID: records currently require exactly one governed dataset.")
        if not plan.fields:
            raise ValueError("PLAN_INVALID: records require explicit fields.")
        dataset = datasets[0]
        fields = tuple(self._field_name(value) for value in plan.fields)
        for field in fields:
            catalog.field_owner(field, datasets)
        where, parameters = self._filters(plan.filters, catalog, datasets, {dataset: "d0"})
        requested_order = self._normalize_order(plan.order_by, set(fields))
        order = requested_order or ((fields[0], "ASC"),)
        window_order = self._order_sql(order)
        limit_clause, limit_parameters = self._limit(plan)
        sql = f"""
            WITH selected AS (
                SELECT d0.*
                FROM {dataset} AS d0
                WHERE {where}
            ),
            ranked AS (
                SELECT selected.*,
                       COUNT(*) OVER () AS _total_rows,
                       ROW_NUMBER() OVER (ORDER BY {window_order}) AS _result_rank
                FROM selected
                WHERE 1 = 1
            )
            SELECT {', '.join(fields)}, _total_rows, _result_rank
            FROM ranked
            ORDER BY _result_rank{limit_clause}
        """
        return CompiledSemanticQuery(
            SQLProposal(
                sql,
                (*parameters, *limit_parameters),
                "Generic records operator compiled from K-Graph fields.",
            ),
            plan,
            (*fields, "_total_rows", "_result_rank"),
            order,
        )

    def _compile_aggregate(
        self,
        plan: SemanticQueryPlan,
        catalog: _Catalog,
        datasets: tuple[str, ...],
    ) -> CompiledSemanticQuery:
        aliases = {dataset: f"d{index}" for index, dataset in enumerate(datasets)}
        from_sql = self._from_sql(datasets, aliases, catalog)
        base_dimensions = tuple(self._field_name(value) for value in plan.dimensions)
        dimension_sql = [
            f"{aliases[catalog.field_owner(name, datasets)]}.{name} AS {name}"
            for name in base_dimensions
        ]
        group_expressions = [
            f"{aliases[catalog.field_owner(name, datasets)]}.{name}"
            for name in base_dimensions
        ]
        dimensions = base_dimensions
        if plan.time_bucket:
            bucket_name = self._field_name(str(plan.time_bucket.get("name", "period")))
            if bucket_name in base_dimensions:
                raise ValueError("PLAN_INVALID: time bucket name duplicates a dimension.")
            bucket_expression = self._time_bucket_expression(
                plan.time_bucket, catalog, datasets, aliases
            )
            dimension_sql.append(f"{bucket_expression} AS {bucket_name}")
            group_expressions.append(bucket_expression)
            dimensions = (*base_dimensions, bucket_name)
        metric_sql = [
            f"{catalog.metric_expression(name, aliases)} AS {name}" for name in plan.metrics
        ]
        where, parameters = self._filters(plan.filters, catalog, datasets, aliases)
        group_by = ""
        if dimensions:
            group_by = "\n                GROUP BY " + ", ".join(group_expressions)
        selected = ",\n                       ".join((*dimension_sql, *metric_sql))
        ctes = [
            f"""grouped AS (
                SELECT {selected}
                FROM {from_sql}
                WHERE {where}{group_by}
            )"""
        ]
        parameter_values: list[Any] = list(parameters)
        available = set(dimensions) | set(plan.metrics)
        units = {
            name: catalog.metric(name).get("unit", "unknown") for name in plan.metrics
        }
        stage = "grouped"
        calculation_names: list[str] = []
        for index, calculation in enumerate(plan.calculations, start=1):
            name = self._field_name(str(calculation.get("name", "")))
            if name in available:
                raise ValueError(f"PLAN_INVALID: duplicate calculation name {name!r}.")
            expression, calculation_parameters, unit = self._calculation_expression(
                calculation, available, units
            )
            next_stage = f"calculated_{index}"
            ctes.append(
                f"""{next_stage} AS (
                SELECT {stage}.*, {expression} AS {name}
                FROM {stage}
                WHERE 1 = 1
            )"""
            )
            parameter_values.extend(calculation_parameters)
            available.add(name)
            units[name] = unit
            calculation_names.append(name)
            stage = next_stage

        window_names: list[str] = []
        for index, window in enumerate(plan.window_calculations, start=1):
            name = self._field_name(str(window.get("name", "")))
            if name in available:
                raise ValueError(f"PLAN_INVALID: duplicate window name {name!r}.")
            expression, unit = self._window_expression(window, available, units)
            next_stage = f"windowed_{index}"
            ctes.append(
                f"""{next_stage} AS (
                SELECT {stage}.*, {expression} AS {name}
                FROM {stage}
                WHERE 1 = 1
            )"""
            )
            available.add(name)
            units[name] = unit
            window_names.append(name)
            stage = next_stage

        statistic_names: list[str] = []
        for index, statistic in enumerate(plan.statistics, start=1):
            names, stage = self._append_statistic_ctes(
                statistic,
                index=index,
                stage=stage,
                ctes=ctes,
                available=available,
                units=units,
            )
            statistic_names.extend(names)

        comparison_margin = None
        if plan.comparison:
            left = str(plan.comparison.get("left", ""))
            operator = str(plan.comparison.get("operator", ""))
            if left not in available or operator not in _COMPARISON_OPERATORS:
                raise ValueError("PLAN_INVALID: aggregate comparison is not valid.")
            if "right" in plan.comparison:
                right = str(plan.comparison["right"])
                if right not in available:
                    raise ValueError("PLAN_INVALID: comparison references an unknown value.")
                if units.get(left) != units.get(right):
                    raise ValueError("PLAN_INVALID: comparison values have incompatible units.")
                right_sql = right
                comparison_parameters: tuple[Any, ...] = ()
            elif "right_value" in plan.comparison:
                right_sql = "?"
                comparison_parameters = (plan.comparison["right_value"],)
            else:
                raise ValueError("PLAN_INVALID: comparison requires right or right_value.")
            comparison_margin = "comparison_margin"
            margin = (
                f"{left} - {right_sql}"
                if operator in {">", ">="}
                else f"{right_sql} - {left}"
            )
            ctes.append(
                f"""qualified AS (
                SELECT {stage}.*, ABS({margin}) AS {comparison_margin}
                FROM {stage}
                WHERE {left} {operator} {right_sql}
            )"""
            )
            parameter_values.extend(comparison_parameters)
            parameter_values.extend(comparison_parameters)
            available.add(comparison_margin)
            stage = "qualified"

        order = self._normalize_order(plan.order_by, available)
        if not order:
            order = ((plan.metrics[0], "DESC"), *tuple((name, "ASC") for name in dimensions))
        window_order = self._order_sql(order)
        output = (
            *dimensions,
            *plan.metrics,
            *calculation_names,
            *window_names,
            *statistic_names,
            *((comparison_margin,) if comparison_margin else ()),
        )
        ctes.append(
            f"""ranked AS (
                SELECT {stage}.*,
                       COUNT(*) OVER () AS _total_rows,
                       ROW_NUMBER() OVER (ORDER BY {window_order}) AS _result_rank
                FROM {stage}
                WHERE 1 = 1
            )"""
        )
        limit_clause, limit_parameters = self._limit(plan)
        cte_sql = ",\n            ".join(ctes)
        sql = f"""
            WITH {cte_sql}
            SELECT {', '.join(output)}, _total_rows, _result_rank
            FROM ranked
            ORDER BY _result_rank{limit_clause}
        """
        return CompiledSemanticQuery(
            SQLProposal(
                sql,
                (*parameter_values, *limit_parameters),
                "Generic aggregate/calculation operators compiled from K-Graph metrics.",
            ),
            plan,
            (*output, "_total_rows", "_result_rank"),
            order,
        )

    def _calculation_expression(
        self,
        calculation: dict[str, Any],
        available: set[str],
        units: dict[str, str],
    ) -> tuple[str, tuple[Any, ...], str]:
        operator = str(calculation.get("operator", ""))
        left = self._field_name(str(calculation.get("left", "")))
        right = self._field_name(str(calculation.get("right", "")))
        if operator not in _ARITHMETIC_OPERATORS:
            raise ValueError(f"PLAN_INVALID: arithmetic operator {operator!r} is not allowed.")
        if left not in available or right not in available:
            raise ValueError("PLAN_INVALID: calculation references an unknown value.")
        if operator in {"add", "subtract", "absolute_difference"} and units.get(
            left
        ) != units.get(right):
            raise ValueError("PLAN_INVALID: arithmetic values have incompatible units.")
        if operator == "add":
            return f"{left} + {right}", (), units.get(left, "unknown")
        if operator == "subtract":
            return f"{left} - {right}", (), units.get(left, "unknown")
        if operator == "multiply":
            return (
                f"{left} * {right}",
                (),
                f"{units.get(left, 'unknown')}*{units.get(right, 'unknown')}",
            )
        if operator == "absolute_difference":
            return f"ABS({left} - {right})", (), units.get(left, "unknown")
        scale = calculation.get("scale", 1.0)
        if (
            not isinstance(scale, Real)
            or isinstance(scale, bool)
            or not -1_000_000 <= float(scale) <= 1_000_000
        ):
            raise ValueError("PLAN_INVALID: divide scale must be a bounded number.")
        return (
            f"? * {left} / NULLIF({right}, 0)",
            (float(scale),),
            f"{units.get(left, 'unknown')}/{units.get(right, 'unknown')}",
        )

    def _time_bucket_expression(
        self,
        bucket: dict[str, Any],
        catalog: _Catalog,
        datasets: tuple[str, ...],
        aliases: dict[str, str],
    ) -> str:
        field = self._field_name(str(bucket.get("field", "")))
        grain = str(bucket.get("grain", ""))
        owner = catalog.field_owner(field, datasets)
        detail = catalog.field_detail(owner, field)
        if detail["semantic_role"] != "time":
            raise ValueError("PLAN_INVALID: time_bucket requires a time-role field.")
        column = f"{aliases[owner]}.{field}"
        if grain == "year":
            return column if detail["data_type"] == "integer" else f"SUBSTR({column}, 1, 4)"
        if detail["data_type"] != "text":
            raise ValueError("PLAN_INVALID: month/quarter buckets require a date-text field.")
        if grain == "month":
            return f"SUBSTR({column}, 1, 7)"
        if grain == "quarter":
            return (
                f"CAST(SUBSTR({column}, 1, 4) AS INTEGER) * 10 + "
                f"((CAST(SUBSTR({column}, 6, 2) AS INTEGER) - 1) / 3 + 1)"
            )
        raise ValueError("PLAN_INVALID: time bucket grain must be year, quarter, or month.")

    def _window_expression(
        self,
        window: dict[str, Any],
        available: set[str],
        units: dict[str, str],
    ) -> tuple[str, str]:
        operator = str(window.get("operator", ""))
        input_name = self._field_name(str(window.get("input", "")))
        if operator not in _WINDOW_OPERATORS or input_name not in available:
            raise ValueError("PLAN_INVALID: window operator or input is not valid.")
        partition_by = tuple(
            self._field_name(str(value)) for value in (window.get("partition_by") or [])
        )
        if any(value not in available for value in partition_by):
            raise ValueError("PLAN_INVALID: window partition references an unknown value.")
        order_field = self._field_name(str(window.get("order_field", "")))
        direction = str(window.get("direction", "ASC")).upper()
        if order_field not in available or direction not in {"ASC", "DESC"}:
            raise ValueError("PLAN_INVALID: window ordering is not valid.")
        partition_sql = (
            "PARTITION BY " + ", ".join(partition_by) + " " if partition_by else ""
        )
        ordered_window = f"{partition_sql}ORDER BY {order_field} {direction}"
        if operator in {"lag", "lead"}:
            offset = window.get("offset", 1)
            if not isinstance(offset, int) or isinstance(offset, bool) or not 1 <= offset <= 1000:
                raise ValueError("PLAN_INVALID: lag/lead offset must be between 1 and 1000.")
            return (
                f"{operator.upper()}({input_name}, {offset}) OVER ({ordered_window})",
                units.get(input_name, "unknown"),
            )
        frame_size = window.get("window", 3)
        if (
            not isinstance(frame_size, int)
            or isinstance(frame_size, bool)
            or not 1 <= frame_size <= 10_000
        ):
            raise ValueError("PLAN_INVALID: rolling window must be between 1 and 10000.")
        preceding = frame_size - 1
        frame = (
            f"{ordered_window} ROWS BETWEEN {preceding} PRECEDING AND CURRENT ROW"
        )
        if operator == "rolling_sum":
            expression = f"SUM({input_name}) OVER ({frame})"
        elif operator == "rolling_average":
            expression = f"AVG({input_name}) OVER ({frame})"
        else:
            mean = f"AVG({input_name}) OVER ({frame})"
            mean_square = f"AVG({input_name} * {input_name}) OVER ({frame})"
            expression = f"SQRT(MAX({mean_square} - ({mean}) * ({mean}), 0))"
        return expression, units.get(input_name, "unknown")

    def _append_statistic_ctes(
        self,
        statistic: dict[str, Any],
        *,
        index: int,
        stage: str,
        ctes: list[str],
        available: set[str],
        units: dict[str, str],
    ) -> tuple[tuple[str, ...], str]:
        operator = str(statistic.get("operator", ""))
        name = self._field_name(str(statistic.get("name", "")))
        if operator not in _STATISTIC_OPERATORS or name in available:
            raise ValueError("PLAN_INVALID: statistic operator or name is not valid.")
        partition_by = tuple(
            self._field_name(str(value))
            for value in (statistic.get("partition_by") or [])
        )
        if any(value not in available for value in partition_by):
            raise ValueError("PLAN_INVALID: statistic partition references unknown values.")
        partition = "PARTITION BY " + ", ".join(partition_by) if partition_by else ""

        if operator == "correlation":
            left = self._field_name(str(statistic.get("left", "")))
            right = self._field_name(str(statistic.get("right", "")))
            if left not in available or right not in available:
                raise ValueError("PLAN_INVALID: correlation inputs are unknown.")
            count = f"COUNT(*) OVER ({partition})"
            sum_left = f"SUM({left}) OVER ({partition})"
            sum_right = f"SUM({right}) OVER ({partition})"
            numerator = (
                f"{count} * SUM({left} * {right}) OVER ({partition}) - "
                f"({sum_left}) * ({sum_right})"
            )
            left_term = (
                f"{count} * SUM({left} * {left}) OVER ({partition}) - "
                f"({sum_left}) * ({sum_left})"
            )
            right_term = (
                f"{count} * SUM({right} * {right}) OVER ({partition}) - "
                f"({sum_right}) * ({sum_right})"
            )
            expression = f"1.0 * ({numerator}) / NULLIF(SQRT(({left_term}) * ({right_term})), 0)"
            unit = "correlation"
        else:
            input_name = self._field_name(str(statistic.get("input", "")))
            if input_name not in available:
                raise ValueError("PLAN_INVALID: statistic input is unknown.")
            if operator == "z_score":
                mean = f"AVG({input_name}) OVER ({partition})"
                mean_square = f"AVG({input_name} * {input_name}) OVER ({partition})"
                stddev = f"SQRT(MAX({mean_square} - ({mean}) * ({mean}), 0))"
                expression = f"({input_name} - ({mean})) / NULLIF({stddev}, 0)"
                unit = "standard_deviation"
            elif operator == "percentile":
                expression = (
                    f"PERCENT_RANK() OVER ({partition + ' ' if partition else ''}"
                    f"ORDER BY {input_name})"
                )
                unit = "proportion"
            elif operator == "trend_slope":
                time_name = self._field_name(str(statistic.get("time", "")))
                if time_name not in available:
                    raise ValueError("PLAN_INVALID: trend time input is unknown.")
                count = f"COUNT(*) OVER ({partition})"
                sum_time = f"SUM({time_name}) OVER ({partition})"
                numerator = (
                    f"{count} * SUM({time_name} * {input_name}) OVER ({partition}) - "
                    f"({sum_time}) * SUM({input_name}) OVER ({partition})"
                )
                denominator = (
                    f"{count} * SUM({time_name} * {time_name}) OVER ({partition}) - "
                    f"({sum_time}) * ({sum_time})"
                )
                expression = f"1.0 * ({numerator}) / NULLIF({denominator}, 0)"
                unit = f"{units.get(input_name, 'unknown')}/time"
            else:
                if partition_by:
                    raise ValueError("PLAN_INVALID: iqr_outlier currently requires no partition.")
                quartile_stage = f"quartiled_{index}"
                bounds_stage = f"iqr_bounds_{index}"
                result_stage = f"statistic_{index}"
                q1_name = f"{name}_q1"
                q3_name = f"{name}_q3"
                ctes.extend(
                    (
                        f"""{quartile_stage} AS (
                SELECT {stage}.*, NTILE(4) OVER (ORDER BY {input_name}) AS _quartile_{index}
                FROM {stage}
                WHERE 1 = 1
            )""",
                        f"""{bounds_stage} AS (
                SELECT MAX(CASE WHEN _quartile_{index} = 1 THEN {input_name} END) AS {q1_name},
                       MIN(CASE WHEN _quartile_{index} = 4 THEN {input_name} END) AS {q3_name}
                FROM {quartile_stage}
                WHERE 1 = 1
            )""",
                        f"""{result_stage} AS (
                SELECT {quartile_stage}.*,
                       {bounds_stage}.{q1_name},
                       {bounds_stage}.{q3_name},
                       CASE WHEN {input_name} < {bounds_stage}.{q1_name} - 1.5 * ({bounds_stage}.{q3_name} - {bounds_stage}.{q1_name})
                                  OR {input_name} > {bounds_stage}.{q3_name} + 1.5 * ({bounds_stage}.{q3_name} - {bounds_stage}.{q1_name})
                            THEN 1 ELSE 0 END AS {name}
                FROM {quartile_stage}
                CROSS JOIN {bounds_stage}
                WHERE 1 = 1
            )""",
                    )
                )
                available.update((name, q1_name, q3_name))
                units.update(
                    {
                        name: "boolean",
                        q1_name: units.get(input_name, "unknown"),
                        q3_name: units.get(input_name, "unknown"),
                    }
                )
                return (name, q1_name, q3_name), result_stage

        next_stage = f"statistic_{index}"
        ctes.append(
            f"""{next_stage} AS (
                SELECT {stage}.*, {expression} AS {name}
                FROM {stage}
                WHERE 1 = 1
            )"""
        )
        available.add(name)
        units[name] = unit
        return (name,), next_stage

    def _compile_endpoint_growth(
        self,
        plan: SemanticQueryPlan,
        catalog: _Catalog,
        datasets: tuple[str, ...],
    ) -> CompiledSemanticQuery:
        if plan.start_year is None or plan.end_year is None or plan.start_year >= plan.end_year:
            raise ValueError("PLAN_INVALID: endpoint transform requires ordered start/end years.")
        if not plan.dimensions:
            raise ValueError("PLAN_INVALID: endpoint transform requires entity dimensions.")
        if len(plan.metrics) < 1:
            raise ValueError("PLAN_INVALID: endpoint transform requires at least one metric.")
        aliases = {dataset: f"d{index}" for index, dataset in enumerate(datasets)}
        from_sql = self._from_sql(datasets, aliases, catalog)
        dimensions = tuple(self._field_name(value) for value in plan.dimensions)
        dimension_sources = {
            name: f"{aliases[catalog.field_owner(name, datasets)]}.{name}" for name in dimensions
        }
        time_field = catalog.common_field_by_role("time", datasets)
        time_owner = catalog.field_owner(time_field, datasets)
        yearly_select = [f"{source} AS {name}" for name, source in dimension_sources.items()]
        yearly_select.append(f"{aliases[time_owner]}.{time_field} AS {time_field}")
        yearly_select.extend(
            f"{catalog.metric_expression(name, aliases)} AS {name}" for name in plan.metrics
        )
        filters = tuple(plan.filters) + (
            {
                "field": time_field,
                "operator": ">=",
                "value": plan.start_year,
            },
            {
                "field": time_field,
                "operator": "<=",
                "value": plan.end_year,
            },
        )
        where, parameters = self._filters(filters, catalog, datasets, aliases)
        yearly_group = ", ".join(
            (*dimension_sources.values(), f"{aliases[time_owner]}.{time_field}")
        )

        endpoint_columns: list[str] = []
        scored_columns: list[str] = []
        output_columns: list[str] = list(dimensions)
        transformed_aliases: dict[str, str] = {}
        endpoint_parameters: list[Any] = []
        for metric in plan.metrics:
            start = f"{metric}_start"
            end = f"{metric}_end"
            suffix = {
                "endpoint_change": "change",
                "endpoint_growth_pct": "growth_pct",
                "endpoint_ratio": "ratio",
            }[plan.transform]
            transformed = f"{metric}_{suffix}"
            formula = {
                "endpoint_change": f"{end} - {start}",
                "endpoint_growth_pct": f"100.0 * ({end} - {start}) / {start}",
                "endpoint_ratio": f"1.0 * {end} / {start}",
            }[plan.transform]
            endpoint_columns.extend(
                (
                    f"MAX(CASE WHEN {time_field} = ? THEN {metric} END) AS {start}",
                    f"MAX(CASE WHEN {time_field} = ? THEN {metric} END) AS {end}",
                )
            )
            endpoint_parameters.extend((plan.start_year, plan.end_year))
            scored_columns.extend(
                (
                    start,
                    end,
                    f"{formula} AS {transformed}",
                )
            )
            output_columns.extend((start, end, transformed))
            transformed_aliases[metric] = transformed

        comparison_sql = "1 = 1"
        margin_expression = "0.0"
        if plan.comparison:
            left = str(plan.comparison.get("left_metric", ""))
            right = str(plan.comparison.get("right_metric", ""))
            operator = str(plan.comparison.get("operator", ""))
            if left not in transformed_aliases or right not in transformed_aliases:
                raise ValueError("PLAN_INVALID: comparison references an unselected metric.")
            if operator not in _COMPARISON_OPERATORS:
                raise ValueError("PLAN_INVALID: comparison operator is not allowed.")
            comparison_sql = (
                f"{transformed_aliases[left]} {operator} {transformed_aliases[right]}"
            )
            if operator in {">", ">="}:
                margin_expression = (
                    f"{transformed_aliases[left]} - {transformed_aliases[right]}"
                )
            else:
                margin_expression = (
                    f"{transformed_aliases[right]} - {transformed_aliases[left]}"
                )
            margin_name = (
                "comparison_margin_pct_points"
                if plan.transform == "endpoint_growth_pct"
                else "comparison_margin"
            )
            output_columns.append(margin_name)
        else:
            margin_name = "comparison_margin"

        dimension_list = ", ".join(dimensions)
        endpoints_select = ",\n                       ".join((*dimensions, *endpoint_columns))
        scored_select = ",\n                       ".join((*dimensions, *scored_columns))
        baseline_condition = (
            " > 0" if plan.transform == "endpoint_growth_pct" else " != 0"
            if plan.transform == "endpoint_ratio"
            else " IS NOT NULL"
        )
        positive_endpoints = " AND ".join(
            f"{metric}_start IS NOT NULL AND {metric}_end IS NOT NULL AND "
            f"{metric}_start{baseline_condition}"
            for metric in plan.metrics
        )
        rounded_outputs = [*dimensions]
        for metric in plan.metrics:
            rounded_outputs.extend(
                (
                    f"{metric}_start",
                    f"{metric}_end",
                    f"ROUND({transformed_aliases[metric]}, 2) "
                    f"AS {transformed_aliases[metric]}",
                )
            )
        if plan.comparison:
            rounded_outputs.append(
                f"ROUND({margin_expression}, 2) AS {margin_name}"
            )
        allowed_order = set(output_columns)
        order = self._normalize_order(plan.order_by, allowed_order)
        if not order:
            default_field = (
                margin_name
                if plan.comparison
                else transformed_aliases[plan.metrics[0]]
            )
            order = ((default_field, "DESC"), *tuple((name, "ASC") for name in dimensions))
        elif not any(name in dimensions for name, _ in order):
            order = (*order, *tuple((name, "ASC") for name in dimensions))
        window_order = ", ".join(
            f"{f'ROUND({margin_expression}, 2)' if field == margin_name and plan.comparison else field} {direction}"
            for field, direction in order
        )
        ranked_select = ",\n                       ".join(rounded_outputs)
        limit_clause, limit_parameters = self._limit(plan)
        sql = f"""
            WITH yearly AS (
                SELECT {', '.join(yearly_select)}
                FROM {from_sql}
                WHERE {where}
                GROUP BY {yearly_group}
            ),
            endpoints AS (
                SELECT {endpoints_select}
                FROM yearly
                WHERE 1 = 1
                GROUP BY {dimension_list}
            ),
            scored AS (
                SELECT {scored_select}
                FROM endpoints
                WHERE {positive_endpoints}
            ),
            qualified AS (
                SELECT scored.*
                FROM scored
                WHERE {comparison_sql}
            ),
            ranked AS (
                SELECT {ranked_select},
                       COUNT(*) OVER () AS _total_rows,
                       ROW_NUMBER() OVER (ORDER BY {window_order}) AS _result_rank
                FROM qualified
                WHERE 1 = 1
            )
            SELECT {', '.join(output_columns)}, _total_rows, _result_rank
            FROM ranked
            ORDER BY _result_rank{limit_clause}
        """
        return CompiledSemanticQuery(
            SQLProposal(
                sql,
                (*parameters, *endpoint_parameters, *limit_parameters),
                "Generic endpoint transform compiled from K-Graph metrics and join paths.",
            ),
            plan,
            (*output_columns, "_total_rows", "_result_rank"),
            order,
        )

    @staticmethod
    def _field_name(value: str) -> str:
        name = value.rsplit(".", 1)[-1]
        if not _IDENTIFIER.fullmatch(name):
            raise ValueError(f"PLAN_INVALID: unsafe field name {value!r}.")
        return name

    def _filters(
        self,
        filters: tuple[dict[str, Any], ...],
        catalog: _Catalog,
        datasets: tuple[str, ...],
        aliases: dict[str, str],
    ) -> tuple[str, tuple[Any, ...]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        for item in filters:
            field = self._field_name(str(item.get("field", "")))
            operator = str(item.get("operator", "")).lower()
            if operator not in _FILTER_OPERATORS:
                raise ValueError(f"PLAN_INVALID: filter operator {operator!r} is not allowed.")
            owner = catalog.field_owner(field, datasets)
            column = f"{aliases[owner]}.{field}"
            value = item.get("value")
            if operator in {"is_null", "is_not_null"}:
                clauses.append(f"{column} IS {'NOT ' if operator == 'is_not_null' else ''}NULL")
            elif operator == "between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError("PLAN_INVALID: BETWEEN requires two boundary values.")
                clauses.append(f"{column} BETWEEN ? AND ?")
                parameters.extend(value)
            elif operator == "in":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValueError("PLAN_INVALID: IN requires a non-empty value list.")
                clauses.append(f"{column} IN ({', '.join('?' for _ in value)})")
                parameters.extend(value)
            elif operator == "contains":
                clauses.append(f"{column} LIKE ?")
                parameters.append(f"%{value}%")
            else:
                clauses.append(f"{column} {operator} ?")
                parameters.append(value)
        return (" AND ".join(clauses) if clauses else "1 = 1", tuple(parameters))

    @staticmethod
    def _normalize_order(
        requested: tuple[dict[str, str], ...], allowed: set[str]
    ) -> tuple[tuple[str, str], ...]:
        result: list[tuple[str, str]] = []
        for item in requested:
            field = str(item.get("field", ""))
            direction = str(item.get("direction", "ASC")).upper()
            if field not in allowed or direction not in {"ASC", "DESC"}:
                raise ValueError("PLAN_INVALID: order field or direction is not allowed.")
            result.append((field, direction))
        return tuple(result)

    @staticmethod
    def _order_sql(order: tuple[tuple[str, str], ...]) -> str:
        return ", ".join(f"{field} {direction}" for field, direction in order)

    @staticmethod
    def _limit(plan: SemanticQueryPlan) -> tuple[str, tuple[Any, ...]]:
        if plan.result_limit is None:
            return "", ()
        return "\n            LIMIT ?", (plan.result_limit,)

    @staticmethod
    def _from_sql(
        datasets: tuple[str, ...], aliases: dict[str, str], catalog: _Catalog
    ) -> str:
        first = datasets[0]
        sql = f"{first} AS {aliases[first]}"
        joined = {first}
        for dataset in datasets[1:]:
            link = catalog.join_link(joined, dataset)
            if link["left_dataset"] in joined:
                existing = link["left_dataset"]
                incoming = link["right_dataset"]
                pairs = link["keys"]
            else:
                existing = link["right_dataset"]
                incoming = link["left_dataset"]
                pairs = [(right, left) for left, right in link["keys"]]
            if incoming != dataset:
                raise ValueError("PLAN_INVALID: dataset join path is inconsistent.")
            conditions = " AND ".join(
                f"{aliases[existing]}.{left} = {aliases[incoming]}.{right}"
                for left, right in pairs
            )
            sql += f"\n                JOIN {dataset} AS {aliases[dataset]} ON {conditions}"
            joined.add(dataset)
        return sql


class _Catalog:
    def __init__(self, context: GraphContext) -> None:
        self.datasets = {dataset.name: dataset for dataset in context.datasets}
        self.dataset_names = set(self.datasets)
        self.metrics = {metric["name"]: metric for metric in context.metrics}
        self.joins = context.dataset_joins

    def metric(self, name: str) -> dict[str, str]:
        try:
            return self.metrics[name]
        except KeyError as exc:
            raise ValueError(f"PLAN_INVALID: metric {name!r} is absent from graph context.") from exc

    def field_owner(self, field: str, datasets: tuple[str, ...]) -> str:
        owners = [
            dataset
            for dataset in datasets
            if field in {item["column_name"] for item in self.datasets[dataset].fields}
        ]
        if not owners:
            raise ValueError(f"PLAN_INVALID: field {field!r} is absent from selected datasets.")
        return owners[0]

    def field_detail(self, dataset: str, field: str) -> dict[str, str]:
        try:
            return next(
                item
                for item in self.datasets[dataset].fields
                if item["column_name"] == field
            )
        except (KeyError, StopIteration) as exc:
            raise ValueError(
                f"PLAN_INVALID: field {field!r} is absent from dataset {dataset!r}."
            ) from exc

    def common_field_by_role(self, role: str, datasets: tuple[str, ...]) -> str:
        candidates: set[str] | None = None
        for dataset in datasets:
            fields = {
                item["column_name"]
                for item in self.datasets[dataset].fields
                if item["semantic_role"] == role
            }
            candidates = fields if candidates is None else candidates & fields
        if not candidates or len(candidates) != 1:
            raise ValueError(
                f"PLAN_INVALID: selected datasets require one common {role!r} field."
            )
        return next(iter(candidates))

    def metric_expression(self, name: str, aliases: dict[str, str]) -> str:
        metric = self.metric(name)
        dataset = metric["dataset_name"]
        if dataset not in aliases:
            raise ValueError(f"PLAN_INVALID: metric {name!r} dataset was not selected.")
        expression = metric["expression"]
        if not _EXPRESSION.fullmatch(expression) or any(
            marker in expression for marker in ("--", "/*", "*/", ";", "'")
        ):
            raise ValueError(f"GRAPH_METADATA_INVALID: unsafe metric expression for {name!r}.")
        fields = {item["column_name"] for item in self.datasets[dataset].fields}

        def replace(match: re.Match[str]) -> str:
            token = match.group(0)
            if token.upper() in _SQL_WORDS:
                return token
            if token in fields:
                return f"{aliases[dataset]}.{token}"
            raise ValueError(
                f"GRAPH_METADATA_INVALID: metric {name!r} references unknown token {token!r}."
            )

        return _WORDS.sub(replace, expression)

    def join_link(self, joined: set[str], incoming: str) -> dict[str, Any]:
        candidates = [
            row
            for row in self.joins
            if (
                row["left_dataset"] in joined and row["right_dataset"] == incoming
            )
            or (
                row["right_dataset"] in joined and row["left_dataset"] == incoming
            )
        ]
        if len(candidates) != 1:
            raise ValueError(
                "PLAN_INVALID: selected datasets lack one unambiguous K-Graph join path."
            )
        return candidates[0]
