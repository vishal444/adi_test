from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from kgraph_llm.core import GraphContext, QuestionSpec
from kgraph_llm.llm_control import LLMError, make_llm
from kgraph_llm.llm_control.google_provider import GoogleGeminiLLM


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self, _amount: int | None = None) -> bytes:
        return self.payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class GoogleGeminiLLMTest(unittest.TestCase):
    def test_factory_loads_cwd_dotenv_without_overriding_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text(
                "GEMINI_API_KEY=file-key\nGEMINI_MODEL=gemini-3.5-flash-lite\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GEMINI_API_KEY": "shell-key"}, clear=True):
                with patch(
                    "kgraph_llm.llm_control.factory.Path.cwd",
                    return_value=Path(directory),
                ):
                    adapter = make_llm("google")
        self.assertEqual(adapter.api_key, "shell-key")
        self.assertEqual(adapter.model, "gemini-3.5-flash-lite")

    def test_requires_environment_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMError):
                GoogleGeminiLLM()

    def test_generate_content_request_uses_header_and_parses_json(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["key"] = request.get_header("X-goog-api-key")
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": '{"findings":"bounded result"}'}]
                            }
                        }
                    ]
                }
            )

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test"},
            clear=True,
        ):
            adapter = GoogleGeminiLLM()
            with patch("urllib.request.urlopen", fake_urlopen):
                result = adapter._request_json("Return JSON", "Test input")

        self.assertEqual(result, {"findings": "bounded result"})
        self.assertEqual(captured["key"], "test-key")
        self.assertIn("gemini-test:generateContent", str(captured["url"]))
        self.assertEqual(captured["timeout"], 60)
        body = captured["body"]
        self.assertEqual(body["system_instruction"]["parts"][0]["text"], "Return JSON")
        self.assertEqual(
            body["generationConfig"]["responseFormat"]["text"]["mimeType"],
            "APPLICATION_JSON",
        )

    def test_google_http_error_message_is_exposed_but_key_is_redacted(self) -> None:
        response = BytesIO(
            json.dumps(
                {
                    "error": {
                        "status": "INVALID_ARGUMENT",
                        "message": "Invalid request made with test-secret-key",
                    }
                }
            ).encode("utf-8")
        )
        error = urllib.error.HTTPError(
            "https://example.invalid",
            400,
            "Bad Request",
            {},
            response,
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret-key"}, clear=True):
            adapter = GoogleGeminiLLM()
            detail = adapter._http_error_detail(error)
        self.assertIn("INVALID_ARGUMENT", detail)
        self.assertIn("[REDACTED]", detail)
        self.assertNotIn("test-secret-key", detail)

    def test_plan_query_requests_semantic_plan_not_sql(self) -> None:
        response = {
            "operation": "aggregate",
            "datasets": ["approved_view"],
            "dimensions": ["district_name"],
            "metrics": ["hospital_count"],
            "transform": "none",
            "comparison": {},
            "order_by": [{"field": "hospital_count", "direction": "DESC"}],
        }
        context = GraphContext(
            entities=(),
            datasets=(),
            metrics=(),
            relationships=(),
            dataset_joins=(),
            registry_version="test",
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            adapter = GoogleGeminiLLM()
            with patch.object(adapter, "_request_json", return_value=response) as request:
                plan = adapter.plan_query(QuestionSpec("Count hospitals"), context)
        instructions = request.call_args.args[0]
        request_payload = json.loads(request.call_args.args[1])
        self.assertIn("never SQL", instructions)
        self.assertNotIn("query_engine_capabilities", request_payload)
        self.assertEqual(
            set(request_payload), {"question_spec", "semantic_graph"}
        )
        self.assertEqual(plan.operation, "aggregate")
        self.assertEqual(plan.metrics, ("hospital_count",))


if __name__ == "__main__":
    unittest.main()
