from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..core.contracts import GraphContext, QuestionSpec, SemanticQueryPlan
from .base import LLMAdapter, LLMError


class GoogleGeminiLLM(LLMAdapter):
    """Google Gemini GenerateContent adapter with JSON-only responses."""

    name = "google-gemini"

    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "GOOGLE_API_KEY"
        )
        if not self.api_key:
            raise LLMError(
                "GEMINI_API_KEY is required for --provider google."
            )
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.base_url = os.environ.get(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")

    def _request_json(self, instructions: str, input_text: str) -> dict[str, Any]:
        model = urllib.parse.quote(self.model, safe="-._")
        payload = {
            "system_instruction": {"parts": [{"text": instructions}]},
            "contents": [
                {"role": "user", "parts": [{"text": input_text}]}
            ],
            "generationConfig": {
                "responseFormat": {"text": {"mimeType": "APPLICATION_JSON"}}
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/models/{model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = self._http_error_detail(exc)
            raise LLMError(
                f"Gemini request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc

        try:
            parts = body["candidates"][0]["content"]["parts"]
            text = "".join(
                str(part.get("text", ""))
                for part in parts
                if isinstance(part, dict)
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini response did not contain generated text.") from exc
        if not text.strip():
            raise LLMError("Gemini response did not contain generated text.")
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Gemini did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise LLMError("Gemini JSON response must be an object.")
        return result

    def _http_error_detail(self, error: urllib.error.HTTPError) -> str:
        """Return a bounded Google error message with the configured key redacted."""
        detail = str(error.reason or "request rejected")
        try:
            payload = json.loads(error.read(8_192).decode("utf-8", errors="replace"))
            google_error = payload.get("error", {})
            status = str(google_error.get("status", "")).strip()
            message = str(google_error.get("message", "")).strip()
            if message:
                detail = f"{status}: {message}" if status else message
        except (AttributeError, json.JSONDecodeError, OSError):
            pass
        if self.api_key:
            detail = detail.replace(self.api_key, "[REDACTED]")
        return detail[:1_000]

    def interpret(self, question: str) -> QuestionSpec:
        data = self._request_json(
            """Convert the user question into one JSON object only. Keys: entity_type (string),
metric_terms (array of snake_case base domain measures only; exclude requested analytical
methods, operators, and derived-output names), comparison (string), start_year (integer or null),
end_year (integer or null), purpose (string), consequence_class (low|medium|high),
filters (object), defaulted_fields (array of disclosed registered defaults),
ambiguity_flags (array of strings). Do not write SQL and do not invent resolved
values when the question is materially ambiguous. Platform semantic default: when a question
supplies exactly two endpoint years and asks for growth, interpret growth as endpoint percentage
change ((end - start) / start * 100), disclose transform=endpoint_growth_pct in defaulted_fields,
and do not flag the growth calculation as ambiguous unless the user requests another method.
Semantic K-Graph path and neighborhood traversal are supported analysis types: when the user
explicitly requests one and names the required endpoint(s), do not flag the absence of a database
metric or an unspecified relationship predicate as ambiguous. Use the starting entity as
entity_type and allow metric_terms to be empty. ambiguity_flags must contain only unresolved
choices that materially change the result; never use them for capability concerns or merely
because the request is a graph traversal or explicitly named analytical method.""",
            question,
        )
        return QuestionSpec(
            original_question=question,
            purpose=str(data.get("purpose", "exploratory_analysis")),
            consequence_class=str(data.get("consequence_class", "low")),
            entity_type=str(data.get("entity_type", "")),
            metric_terms=tuple(str(value) for value in data.get("metric_terms", [])),
            comparison=str(data.get("comparison", "")),
            start_year=data.get("start_year"),
            end_year=data.get("end_year"),
            filters={str(key): str(value) for key, value in data.get("filters", {}).items()},
            defaulted_fields=tuple(str(value) for value in data.get("defaulted_fields", [])),
            ambiguity_flags=tuple(str(value) for value in data.get("ambiguity_flags", [])),
        )

    def plan_query(
        self, spec: QuestionSpec, context: GraphContext
    ) -> SemanticQueryPlan:
        data = self._request_json(
            """Create a semantic query plan, never SQL. Use only exact dataset, metric, field,
entity, and relationship names present in semantic_graph. Return one JSON object with:
operation (records|aggregate|data_quality|graph),
datasets (array), dimensions (array), metrics (array), fields (array), filters (array of
{field,operator,value}; operators =, !=, >, >=, <, <=, in, contains, between, is_null,
is_not_null), transform
(none|endpoint_change|endpoint_growth_pct|endpoint_ratio), calculations (ordered array of
{name,operator,left,right,scale}; operator must be add, subtract, multiply, divide, or
absolute_difference), time_bucket ({name,field,grain}; grain year|quarter|month or {}),
window_calculations (ordered array of {name,operator,input,partition_by,order_field,direction,
offset,window}; operator lag|lead|rolling_sum|rolling_average|rolling_stddev), statistics
(ordered array of {name,operator,input,left,right,time,partition_by}; operator
z_score|percentile|iqr_outlier|trend_slope|correlation), data_quality_checks (array of
{name,operator,field}; operator missing_count|missing_pct|distinct_count|duplicate_count|
minimum|maximum|freshness_max), graph_query ({operator,start,end,start_kind,end_kind,direction,
max_depth,edge_types,node_kinds} or {}; graph operator must be graph_path or graph_neighborhood,
direction must be outgoing, incoming, or undirected, and edge_types may contain only
SEMANTIC_RELATION, AVAILABLE_IN, DEFINED_ON, HAS_FIELD, or DATASET_JOIN; start_kind/end_kind
may use entity, dataset, field, metric, alias, or metadata), comparison
({left_metric,operator,right_metric} for endpoint transforms or {left,operator,right|right_value}
for aggregate calculations), order_by (array of {field,direction}), start_year, end_year, and
result_limit (positive integer or null). Use records for governed detail/list queries and
aggregate for governed metrics; use graph only for semantic relationship traversal, not data
aggregation. For endpoint growth comparisons select the source metric names,
set transform=endpoint_growth_pct, provide both years and the comparison direction. The compiler
owns formulas, joins, SQL, ranking, limits, and verification. When grouping by an entity label,
include its available entity_key dimension to preserve stable identity. Valid order fields are
selected fields/dimensions, metric names, <metric>_growth_pct for endpoint transforms, and
comparison_margin_pct_points for comparisons. Arithmetic left/right values must be metric or
earlier-calculation identifiers, never numbers. Express "A per 100 B" as operator=divide,
left=A, right=B, scale=100. For operation=data_quality, select exactly one dataset, put every
inspected field only inside data_quality_checks, allow filters if needed, set transform=none,
and leave dimensions, metrics, fields, calculations, time_bucket, window_calculations,
statistics, graph_query, comparison, and order_by empty. For operation=graph, use graph_query
only and leave every relational/analytical plan block empty. Do not invent schema objects.""",
            json.dumps(
                {
                    "question_spec": spec.to_dict(),
                    "semantic_graph": context.to_dict(),
                }
            ),
        )
        return SemanticQueryPlan.from_dict(data)
