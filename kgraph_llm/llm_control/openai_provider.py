from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ..core.contracts import GraphContext, QuestionSpec, SQLProposal
from .base import LLMAdapter, LLMError


class OpenAIResponsesLLM(LLMAdapter):
    """Optional live adapter using the OpenAI Responses API and JSON-only prompts."""

    name = "openai-responses"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is required for --provider openai.")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def _request_json(self, instructions: str, input_text: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "reasoning": {"effort": "low"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        text = body.get("output_text")
        if not text:
            for item in body.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text")
                        break
        if not text:
            raise LLMError("The model response did not contain output text.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("The model did not return valid JSON.") from exc

    def interpret(self, question: str) -> QuestionSpec:
        data = self._request_json(
            """Convert the user question into one JSON object only. Keys: entity_type (string),
metric_terms (array of snake_case strings), comparison (string), start_year (integer or null),
end_year (integer or null), purpose (string), consequence_class (low|medium|high),
filters (object), defaulted_fields (array of disclosed registered defaults),
ambiguity_flags (array of strings). Do not write SQL and do not invent resolved
values when the question is materially ambiguous.""",
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

    def generate_sql(self, spec: QuestionSpec, context: GraphContext) -> SQLProposal:
        data = self._request_json(
            """Generate one read-only SQLite SELECT/WITH query using only datasets and columns in
the supplied semantic graph. Return one JSON object only with sql (string), parameters (array),
and rationale (string). Use ? placeholders for all values. Do not use comments, PRAGMA, or any
write/DDL statement. A separate deterministic validator will reject unsafe or unknown objects.""",
            json.dumps({"question_spec": spec.to_dict(), "semantic_graph": context.to_dict()}),
        )
        return SQLProposal(
            sql=str(data.get("sql", "")),
            parameters=tuple(data.get("parameters", [])),
            rationale=str(data.get("rationale", "")),
        )

    def analyze(self, spec: QuestionSpec, rows: tuple[dict[str, Any], ...]) -> str:
        data = self._request_json(
            """Analyze the supplied database result. Return one JSON object only with findings
(string). State only claims supported by the rows, mention material limitations, and never infer
causation, misconduct, or legal conclusions from descriptive associations.""",
            json.dumps({"question_spec": spec.to_dict(), "rows": rows}, default=str),
        )
        return str(data.get("findings", "No findings were produced."))

