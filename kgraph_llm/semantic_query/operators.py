from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OperatorDefinition:
    name: str
    category: str
    status: str
    description: str
    parameters: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


OPERATOR_REGISTRY_VERSION = "semantic-operators-1.2.0"

OPERATORS = (
    OperatorDefinition("records", "relational", "implemented", "Select governed record fields.", ("datasets", "fields")),
    OperatorDefinition("project", "relational", "implemented", "Project approved fields and dimensions.", ("fields",)),
    OperatorDefinition("filter", "relational", "implemented", "Apply bound comparisons, IN, BETWEEN, contains, and null predicates.", ("field", "operator", "value")),
    OperatorDefinition("equijoin", "relational", "implemented", "Join datasets only through K-Graph-approved keys.", ("datasets",)),
    OperatorDefinition("group_by", "aggregation", "implemented", "Group at declared dimensions.", ("dimensions",)),
    OperatorDefinition("governed_metric", "aggregation", "implemented", "Evaluate a K-Graph metric formula and aggregation.", ("metrics",)),
    OperatorDefinition("add", "arithmetic", "implemented", "Add two calculated values.", ("name", "left", "right")),
    OperatorDefinition("subtract", "arithmetic", "implemented", "Subtract the right value from the left value.", ("name", "left", "right")),
    OperatorDefinition("multiply", "arithmetic", "implemented", "Multiply two calculated values.", ("name", "left", "right")),
    OperatorDefinition("divide", "arithmetic", "implemented", "Safely divide two values with a null result for a zero denominator.", ("name", "left", "right", "scale")),
    OperatorDefinition("absolute_difference", "arithmetic", "implemented", "Calculate the absolute difference between values.", ("name", "left", "right")),
    OperatorDefinition("endpoint_change", "time", "implemented", "Calculate absolute change between two endpoints.", ("start_year", "end_year")),
    OperatorDefinition("endpoint_growth_pct", "time", "implemented", "Calculate endpoint percentage growth with a positive baseline.", ("start_year", "end_year")),
    OperatorDefinition("endpoint_ratio", "time", "implemented", "Calculate the end-to-start endpoint ratio.", ("start_year", "end_year")),
    OperatorDefinition("compare", "comparison", "implemented", "Compare metrics, transformations, calculations, or a threshold.", ("left", "operator", "right|right_value")),
    OperatorDefinition("order_by", "result", "implemented", "Order by declared output fields.", ("field", "direction")),
    OperatorDefinition("stable_rank", "result", "implemented", "Assign deterministic contiguous result ranks."),
    OperatorDefinition("top_k", "result", "implemented", "Return the requested first K ranked rows while preserving the full count.", ("result_limit",)),
    OperatorDefinition("exact_result_count", "result", "implemented", "Embed the complete qualifying-row count before truncation."),
    OperatorDefinition("time_bucket", "time", "implemented", "Bucket dates into month, quarter, or year."),
    OperatorDefinition("lag", "window", "implemented", "Read a prior value within an ordered partition."),
    OperatorDefinition("lead", "window", "implemented", "Read a following value within an ordered partition."),
    OperatorDefinition("rolling_sum", "window", "implemented", "Calculate a bounded rolling sum."),
    OperatorDefinition("rolling_average", "window", "implemented", "Calculate a bounded rolling mean."),
    OperatorDefinition("rolling_stddev", "window", "implemented", "Calculate bounded population standard deviation."),
    OperatorDefinition("z_score", "statistics", "implemented", "Standardize deviation from a declared population."),
    OperatorDefinition("percentile", "statistics", "implemented", "Calculate percentile rank within a declared population."),
    OperatorDefinition("iqr_outlier", "statistics", "implemented", "Flag values outside a 1.5-IQR range."),
    OperatorDefinition("trend_slope", "statistics", "implemented", "Estimate a linear time trend."),
    OperatorDefinition("correlation", "statistics", "implemented", "Calculate descriptive correlation without causal claims."),
    OperatorDefinition("missing_count", "data_quality", "implemented", "Count rows with a missing field."),
    OperatorDefinition("missing_pct", "data_quality", "implemented", "Calculate the percentage of rows with a missing field."),
    OperatorDefinition("distinct_count", "data_quality", "implemented", "Count distinct non-null field values."),
    OperatorDefinition("duplicate_count", "data_quality", "implemented", "Count repeated non-null field values."),
    OperatorDefinition("minimum", "data_quality", "implemented", "Calculate a field minimum."),
    OperatorDefinition("maximum", "data_quality", "implemented", "Calculate a field maximum."),
    OperatorDefinition("freshness_max", "data_quality", "implemented", "Return the latest governed time value."),
    OperatorDefinition("graph_path", "graph", "implemented", "Find a bounded shortest path over approved K-Graph edge types."),
    OperatorDefinition("graph_neighborhood", "graph", "implemented", "List nodes in a bounded K-Graph neighborhood."),
)


def operator_capabilities(*, include_planned: bool = False) -> dict[str, object]:
    selected = OPERATORS if include_planned else tuple(
        operator for operator in OPERATORS if operator.status == "implemented"
    )
    return {
        "registry_version": OPERATOR_REGISTRY_VERSION,
        "operators": [operator.to_dict() for operator in selected],
    }
