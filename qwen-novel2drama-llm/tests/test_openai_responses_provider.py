from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.factory import build_provider, generate_with_registry
from providers.openai_responses import OpenAIResponsesProvider


MODEL_INSTANCE = {
    "id": "external.openai.primary",
    "provider": "openai",
    "runtime": "openai_responses",
    "model_name": "${OPENAI_MODEL}",
    "runtime_config": {"api_key_env": "OPENAI_API_KEY", "model_name_env": "OPENAI_MODEL"},
    "capabilities": ["text.chat", "vision.understand", "tool.calling"],
    "input_modalities": ["text", "image", "file"],
    "output_modalities": ["text"],
}


class OpenAIResponsesProviderTests(unittest.TestCase):
    def test_build_payload_maps_text_image_file_and_tools(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, base_url="https://api.example/v1")
        payload = provider.build_payload({
            "request_id": "r1",
            "model": "model.custom",
            "developer": "follow project rules",
            "input": [
                {"type": "text", "text": "hello"},
                {"type": "image", "uri": "https://example.com/a.png", "detail": "high"},
                {"type": "file", "file_id": "file_1", "filename": "a.pdf"},
            ],
            "tools": [{"type": "web_search_preview"}],
            "tool_choice": "auto",
            "max_output_tokens": 100,
        })
        self.assertEqual(payload["model"], "model.custom")
        self.assertEqual(payload["max_output_tokens"], 100)
        self.assertEqual(payload["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(payload["tool_choice"], "auto")
        user_message = payload["input"][-1]
        self.assertEqual(user_message["role"], "user")
        self.assertEqual(user_message["content"][0], {"type": "input_text", "text": "hello"})
        self.assertEqual(user_message["content"][1]["type"], "input_image")
        self.assertEqual(user_message["content"][2]["type"], "input_file")

    def test_dry_run_returns_provider_payload_without_network(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, base_url="https://api.example/v1")
        result = provider.generate({"dry_run": True, "input": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertEqual(result["output"]["url"], "https://api.example/v1/responses")
        self.assertIn("dry_run_no_provider_call", result["warnings"])

    def test_parse_response_extracts_output_text_and_usage(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE)
        result = provider.parse_response({"id": "resp_1", "model": "model.live", "status": "completed", "output_text": "done", "usage": {"input_tokens": 10, "output_tokens": 5}}, {"request_id": "r1"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"]["content"][0]["text"], "done")
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertEqual(result["model"]["provider"], "openai_responses")

    def test_factory_routes_openai_responses_runtime(self) -> None:
        provider = build_provider(MODEL_INSTANCE, base_url="https://api.example/v1")
        self.assertIsInstance(provider, OpenAIResponsesProvider)
        registry = {"instances": [MODEL_INSTANCE]}
        result = generate_with_registry({"model_id": "external.openai.primary", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="https://api.example/v1")
        self.assertEqual(result["model"]["provider"], "openai_responses")

    def test_missing_api_key_fails_before_network(self) -> None:
        old = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            provider = OpenAIResponsesProvider(MODEL_INSTANCE)
            with self.assertRaises(ProviderError) as ctx:
                provider.generate({"input": [{"type": "text", "text": "hello"}]})
            self.assertEqual(ctx.exception.code, "provider_auth_missing")
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
