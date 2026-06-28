from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.tool_loop import generate_provider_round
from providers.base import BaseProvider, ProviderError, continuation_capability
from providers.factory import continuation_capability_with_registry


class DummyProvider(BaseProvider):
    provider_name = "dummy"

    def generate(self, request: dict) -> dict:
        return {"status": "ok", "output": {"content": [{"type": "text", "text": "ok"}]}, "usage": {"total_tokens": 1}}


class ProviderContinuationTests(unittest.TestCase):
    def load_skill_registry(self) -> dict:
        return json.loads((PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json").read_text(encoding="utf-8"))

    def stream_tool_call_chunk(self) -> dict:
        return {
            "chunk_id": "chunk_tool_1",
            "event_type": "provider_stream_tool_call_delta",
            "metadata": {
                "tool_call_partial": {
                    "id": "call_1",
                    "index": 0,
                    "type": "function",
                    "function": {
                        "name": "foundation.token_count",
                        "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}",
                    },
                }
            },
        }

    def test_continuation_capability_defaults_to_unsupported(self) -> None:
        capability = continuation_capability({"id": "m1"})
        self.assertFalse(capability["supported"])
        self.assertEqual(capability["protocol"], "unsupported")
        self.assertEqual(capability["mode"], "fallback_next_provider_request")

    def test_continuation_capability_reads_runtime_config(self) -> None:
        capability = continuation_capability(
            {
                "id": "m1",
                "runtime_config": {
                    "bidirectional_tool_continuation": {
                        "supported": True,
                        "protocol": "realtime_test",
                        "mode": "provider_native",
                    }
                },
            }
        )
        self.assertTrue(capability["supported"])
        self.assertEqual(capability["protocol"], "realtime_test")

    def test_base_provider_default_continuation_raises(self) -> None:
        provider = DummyProvider({"id": "m1"})
        with self.assertRaises(ProviderError) as context:
            list(provider.continue_stream_with_tool_result({}, {"id": "c1"}, {"status": "ok"}))
        self.assertEqual(context.exception.code, "bidirectional_tool_continuation_unsupported")

    def test_factory_reports_continuation_capability(self) -> None:
        registry = {"instances": [{"id": "m1", "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
        capability = continuation_capability_with_registry({"model_id": "m1"}, registry, model_id="m1", base_url="http://example.test/v1")
        self.assertFalse(capability["supported"])
        self.assertEqual(capability["model"]["model_id"], "m1")

    def test_same_stream_request_falls_back_when_provider_unsupported(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            registry = {"instances": [{"id": "m1", "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            completed = {
                "chunk_id": "chunk_done",
                "event_type": "provider_stream_completed",
                "request_id": "r1",
                "model": {"model_id": "m1"},
                "output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}"}}]},
                "metadata": {"tool_call_count": 1},
            }
            chunks = [{"event_type": "provider_stream_started", "request_id": "r1"}, self.stream_tool_call_chunk(), completed]
            chunks_path = Path(tmpdir) / "chunks.jsonl"
            with patch("agent.tool_loop.stream_generate_with_registry", return_value=iter(chunks)):
                response = generate_provider_round(
                    {"request_id": "r1", "model_id": "m1", "input": [{"type": "text", "text": "hello"}]},
                    registry,
                    selected_model_id="m1",
                    stream=True,
                    incremental_tools=True,
                    registry=self.load_skill_registry(),
                    incremental_tool_results_path=Path(tmpdir) / "incremental.json",
                    same_stream_tool_result_injection=True,
                    stream_chunks_path=chunks_path,
                    base_url="http://example.test/v1",
                )
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["stream"]["same_stream_tool_result_injection_requested"])
            self.assertFalse(response["stream"]["same_stream_tool_result_injection_supported"])
            self.assertEqual(response["stream"]["tool_result_event_count"], 1)
            self.assertEqual(response["stream"]["continuation_unsupported_count"], 1)
            text = chunks_path.read_text(encoding="utf-8")
            self.assertIn("provider_stream_tool_result", text)
            self.assertIn("provider_stream_continuation_unsupported", text)


if __name__ == "__main__":
    unittest.main()
