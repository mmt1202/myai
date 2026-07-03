from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.factory import build_provider, generate_with_registry, stream_generate_with_registry
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
    def test_build_payload_maps_text_image_file_tools_and_response_controls(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, base_url="https://api.example/v1")
        payload = provider.build_payload({
            "request_id": "r1",
            "model": "model.custom",
            "developer": "follow project rules",
            "instructions": "be concise",
            "input": [
                {"type": "text", "text": "hello"},
                {"type": "image", "uri": "https://example.com/a.png", "detail": "high"},
                {"type": "file", "file_id": "file_1", "filename": "a.pdf"},
            ],
            "tools": [{"type": "web_search_preview"}],
            "tool_choice": "auto",
            "max_tool_calls": 2,
            "parallel_tool_calls": False,
            "previous_response_id": "resp_prev",
            "prompt_cache_key": "cache-key",
            "prompt_cache_retention": "24h",
            "reasoning": {"effort": "medium"},
            "safety_identifier": "user-hash",
            "service_tier": "default",
            "truncation": "auto",
            "include": ["message.output_text.logprobs"],
            "top_p": 0.9,
            "max_output_tokens": 100,
        })
        self.assertEqual(payload["model"], "model.custom")
        self.assertEqual(payload["instructions"], "be concise")
        self.assertEqual(payload["max_output_tokens"], 100)
        self.assertEqual(payload["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertEqual(payload["max_tool_calls"], 2)
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["previous_response_id"], "resp_prev")
        self.assertEqual(payload["prompt_cache_key"], "cache-key")
        self.assertEqual(payload["prompt_cache_retention"], "24h")
        self.assertEqual(payload["reasoning"], {"effort": "medium"})
        self.assertEqual(payload["safety_identifier"], "user-hash")
        self.assertEqual(payload["service_tier"], "default")
        self.assertEqual(payload["truncation"], "auto")
        self.assertEqual(payload["include"], ["message.output_text.logprobs"])
        self.assertEqual(payload["top_p"], 0.9)
        user_message = payload["input"][-1]
        self.assertEqual(user_message["role"], "user")
        self.assertEqual(user_message["content"][0], {"type": "input_text", "text": "hello"})
        self.assertEqual(user_message["content"][1]["type"], "input_image")
        self.assertEqual(user_message["content"][2]["type"], "input_file")

    def test_build_stream_payload_adds_stream_options(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE)
        payload = provider.build_payload({"stream": True, "stream_include_obfuscation": False, "input": [{"type": "text", "text": "hello"}]})
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["stream_options"], {"include_obfuscation": False})

    def test_generic_model_api_key_does_not_override_registry_openai_key(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, api_key_env="MODEL_API_KEY")
        self.assertEqual(provider.api_key_env, "OPENAI_API_KEY")
        explicit = OpenAIResponsesProvider(MODEL_INSTANCE, api_key_env="CUSTOM_OPENAI_KEY")
        self.assertEqual(explicit.api_key_env, "CUSTOM_OPENAI_KEY")

    def test_dry_run_returns_provider_payload_without_network(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, base_url="https://api.example/v1")
        result = provider.generate({"dry_run": True, "input": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertEqual(result["output"]["url"], "https://api.example/v1/responses")
        self.assertIn("dry_run_no_provider_call", result["warnings"])

    def test_dry_run_native_stream_returns_provider_payload(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE, base_url="https://api.example/v1")
        events = list(provider.stream_generate({"dry_run": True, "input": [{"type": "text", "text": "hello"}]}))
        self.assertEqual(events[0]["event_type"], "provider_stream_started")
        self.assertEqual(events[1]["event_type"], "provider_stream_delta")
        self.assertEqual(events[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(events[-1]["done"])
        self.assertTrue(events[-1]["output"]["provider_payload"]["stream"])

    def test_iter_sse_json_parses_event_and_data(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE)
        lines = [
            b"event: response.output_text.delta\n",
            b"data: {\"delta\": \"he\"}\n",
            b"\n",
            b"data: {\"type\": \"response.output_text.delta\", \"delta\": \"llo\"}\n\n",
            b"data: [DONE]\n\n",
        ]
        items = list(provider.iter_sse_json(lines))
        self.assertEqual(items[0]["type"], "response.output_text.delta")
        self.assertEqual(items[0]["delta"], "he")
        self.assertEqual(items[1]["delta"], "llo")

    def test_stream_event_helpers_map_delta_completed_and_usage(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE)
        delta = {"type": "response.output_text.delta", "delta": "hello"}
        completed = {"type": "response.completed", "response": {"id": "resp_1", "status": "completed", "output_text": "hello", "usage": {"input_tokens": 3, "output_tokens": 2, "output_tokens_details": {"reasoning_tokens": 1}, "input_tokens_details": {"cached_tokens": 2}}}}
        self.assertEqual(provider.stream_delta_from_event(delta), "hello")
        usage = provider.stream_usage_from_event(completed)
        self.assertEqual(usage["input_tokens"], 3)
        self.assertEqual(usage["reasoning_tokens"], 1)
        self.assertEqual(usage["cached_input_tokens"], 2)
        output = provider.stream_output_from_completed_event(completed, ["fallback"])
        self.assertEqual(output["content"][0]["text"], "hello")
        self.assertTrue(provider.is_terminal_stream_event(completed))

    def test_parse_response_extracts_output_text_and_usage(self) -> None:
        provider = OpenAIResponsesProvider(MODEL_INSTANCE)
        result = provider.parse_response({"id": "resp_1", "model": "model.live", "status": "completed", "output_text": "done", "usage": {"input_tokens": 10, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 2}, "input_tokens_details": {"cached_tokens": 3}}}, {"request_id": "r1"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"]["content"][0]["text"], "done")
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertEqual(result["usage"]["reasoning_tokens"], 2)
        self.assertEqual(result["usage"]["cached_input_tokens"], 3)
        self.assertEqual(result["model"]["provider"], "openai_responses")

    def test_factory_routes_openai_responses_runtime(self) -> None:
        provider = build_provider(MODEL_INSTANCE, base_url="https://api.example/v1")
        self.assertIsInstance(provider, OpenAIResponsesProvider)
        registry = {"instances": [MODEL_INSTANCE]}
        result = generate_with_registry({"model_id": "external.openai.primary", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="https://api.example/v1")
        self.assertEqual(result["model"]["provider"], "openai_responses")
        events = list(stream_generate_with_registry({"model_id": "external.openai.primary", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="https://api.example/v1"))
        self.assertEqual(events[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(events[-1]["metadata"]["native_stream"])

    def test_missing_api_key_fails_before_network(self) -> None:
        old = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            provider = OpenAIResponsesProvider(MODEL_INSTANCE)
            with self.assertRaises(ProviderError) as ctx:
                provider.generate({"input": [{"type": "text", "text": "hello"}]})
            self.assertEqual(ctx.exception.code, "provider_auth_missing")
            with self.assertRaises(ProviderError) as stream_ctx:
                list(provider.stream_generate({"input": [{"type": "text", "text": "hello"}]}))
            self.assertEqual(stream_ctx.exception.code, "provider_auth_missing")
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
