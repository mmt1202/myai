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
from providers.factory import continuation_capability_with_registry, continue_stream_with_tool_result_with_registry
from providers.openai_compatible import OpenAICompatibleProvider
from providers.realtime_base import OpenAIResponsesContinuationAdapter, OpenAIRealtimeSessionContinuationAdapter, TestDoubleContinuationAdapter, adapter_for_protocol


class DummyProvider(BaseProvider):
    provider_name = "dummy"

    def generate(self, request: dict) -> dict:
        return {"status": "ok", "output": {"content": [{"type": "text", "text": "ok"}]}, "usage": {"total_tokens": 1}}


class FakeRealtimeSession:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_json(self, event: dict) -> None:
        self.sent.append(event)

    def iter_events(self):
        yield {"type": "response.output_text.delta", "delta": "continued"}
        yield {"type": "response.done"}


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

    def supported_registry(self) -> dict:
        return {
            "instances": [
                {
                    "id": "m1",
                    "provider": "openai_compatible",
                    "runtime": "http_chat_completions",
                    "model_name": "demo",
                    "runtime_config": {"bidirectional_tool_continuation": {"supported": True, "protocol": "provider_native_test", "mode": "provider_native"}},
                }
            ]
        }

    def test_continuation_capability_defaults_to_unsupported(self) -> None:
        capability = continuation_capability({"id": "m1"})
        self.assertFalse(capability["supported"])
        self.assertEqual(capability["protocol"], "unsupported")
        self.assertEqual(capability["mode"], "fallback_next_provider_request")

    def test_continuation_capability_reads_runtime_config(self) -> None:
        capability = continuation_capability({"id": "m1", "runtime_config": {"bidirectional_tool_continuation": {"supported": True, "protocol": "realtime_test", "mode": "provider_native"}}})
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

    def test_realtime_test_double_adapter_emits_native_events(self) -> None:
        adapter = TestDoubleContinuationAdapter(protocol="provider_native_test")
        events = list(adapter.continue_with_tool_result({"request_id": "r1"}, {"model_id": "m1"}, {"id": "call_1", "name": "foundation.token_count"}, {"tool_call_id": "call_1", "status": "ok"}))
        self.assertEqual([event["event_type"] for event in events], ["provider_stream_continuation_started", "provider_stream_continuation_delta", "provider_stream_continuation_completed"])
        self.assertTrue(all((event.get("metadata") or {}).get("provider_native") for event in events))

    def test_adapter_for_protocol_is_explicit(self) -> None:
        self.assertIsNotNone(adapter_for_protocol("provider_native_test"))
        self.assertIsInstance(adapter_for_protocol("openai_responses"), OpenAIResponsesContinuationAdapter)
        self.assertIsInstance(adapter_for_protocol("openai_realtime"), OpenAIRealtimeSessionContinuationAdapter)

    def test_openai_responses_adapter_dry_run_builds_function_call_output(self) -> None:
        adapter = OpenAIResponsesContinuationAdapter(protocol="openai_responses")
        events = list(adapter.continue_with_tool_result({"request_id": "r1", "model": "gpt-test", "dry_run_provider": True, "input": [{"role": "user", "content": "hi"}]}, {"model_id": "m1", "provider_model": "gpt-test"}, {"call_id": "call_1", "name": "tool"}, {"tool_call_id": "call_1", "status": "ok"}))
        self.assertEqual(events[0]["event_type"], "provider_stream_continuation_started")
        self.assertEqual(events[-1]["event_type"], "provider_stream_continuation_completed")
        payload_text = events[1]["delta"]
        self.assertIn("function_call_output", payload_text)
        self.assertIn("/responses", payload_text)

    def test_openai_realtime_adapter_sends_tool_output_to_session(self) -> None:
        adapter = OpenAIRealtimeSessionContinuationAdapter(protocol="openai_realtime")
        session = FakeRealtimeSession()
        events = list(adapter.continue_with_tool_result({"request_id": "r1"}, {"model_id": "m1"}, {"call_id": "call_1", "name": "tool"}, {"tool_call_id": "call_1", "status": "ok"}, {"realtime_session": session}))
        self.assertEqual(session.sent[0]["type"], "conversation.item.create")
        self.assertEqual(session.sent[1]["type"], "response.create")
        self.assertEqual(events[-1]["event_type"], "provider_stream_continuation_completed")
        self.assertIn("continued", events[-1]["output"]["content"][0]["text"])

    def test_openai_compatible_native_continuation_supported_test_protocol(self) -> None:
        provider = OpenAICompatibleProvider(self.supported_registry()["instances"][0], base_url="http://example.test/v1")
        capability = provider.continuation_capability()
        self.assertTrue(capability["supported"])
        self.assertEqual(capability["mode"], "provider_native")
        events = list(provider.continue_stream_with_tool_result({"request_id": "r1"}, {"id": "call_1", "name": "foundation.token_count"}, {"tool_call_id": "call_1", "status": "ok"}))
        self.assertEqual(events[-1]["event_type"], "provider_stream_continuation_completed")

    def test_factory_routes_provider_native_continuation(self) -> None:
        events = list(continue_stream_with_tool_result_with_registry({"request_id": "r1", "model_id": "m1"}, self.supported_registry(), model_id="m1", base_url="http://example.test/v1", tool_call={"id": "call_1", "name": "foundation.token_count"}, tool_result={"tool_call_id": "call_1", "status": "ok"}))
        self.assertEqual(events[0]["event_type"], "provider_stream_continuation_started")
        self.assertEqual(events[-1]["event_type"], "provider_stream_continuation_completed")

    def test_same_stream_request_falls_back_when_provider_unsupported(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            registry = {"instances": [{"id": "m1", "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            completed = {"chunk_id": "chunk_done", "event_type": "provider_stream_completed", "request_id": "r1", "model": {"model_id": "m1"}, "output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}"}}]}, "metadata": {"tool_call_count": 1}}
            chunks = [{"event_type": "provider_stream_started", "request_id": "r1"}, self.stream_tool_call_chunk(), completed]
            chunks_path = Path(tmpdir) / "chunks.jsonl"
            with patch("agent.tool_loop.stream_generate_with_registry", return_value=iter(chunks)):
                response = generate_provider_round({"request_id": "r1", "model_id": "m1", "input": [{"type": "text", "text": "hello"}]}, registry, selected_model_id="m1", stream=True, incremental_tools=True, registry=self.load_skill_registry(), incremental_tool_results_path=Path(tmpdir) / "incremental.json", same_stream_tool_result_injection=True, stream_chunks_path=chunks_path, base_url="http://example.test/v1")
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["stream"]["same_stream_tool_result_injection_requested"])
            self.assertFalse(response["stream"]["same_stream_tool_result_injection_supported"])
            self.assertEqual(response["stream"]["tool_result_event_count"], 1)
            self.assertEqual(response["stream"]["continuation_unsupported_count"], 1)
            text = chunks_path.read_text(encoding="utf-8")
            self.assertIn("provider_stream_tool_result", text)
            self.assertIn("provider_stream_continuation_unsupported", text)

    def test_agent_stream_bridge_uses_provider_native_continuation_when_supported(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            completed = {"chunk_id": "chunk_done", "event_type": "provider_stream_completed", "request_id": "r1", "model": {"model_id": "m1"}, "output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}"}}]}, "metadata": {"tool_call_count": 1}}
            chunks = [{"event_type": "provider_stream_started", "request_id": "r1"}, self.stream_tool_call_chunk(), completed]
            chunks_path = Path(tmpdir) / "chunks.jsonl"
            with patch("agent.tool_loop.stream_generate_with_registry", return_value=iter(chunks)):
                response = generate_provider_round({"request_id": "r1", "model_id": "m1", "input": [{"type": "text", "text": "hello"}]}, self.supported_registry(), selected_model_id="m1", stream=True, incremental_tools=True, registry=self.load_skill_registry(), incremental_tool_results_path=Path(tmpdir) / "incremental.json", same_stream_tool_result_injection=True, stream_chunks_path=chunks_path, base_url="http://example.test/v1")
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["stream"]["same_stream_tool_result_injection_supported"])
            self.assertEqual(response["stream"]["continuation_unsupported_count"], 0)
            self.assertEqual(response["stream"]["provider_native_continuation_completed_count"], 1)
            self.assertGreaterEqual(response["stream"]["provider_native_continuation_event_count"], 3)
            text = chunks_path.read_text(encoding="utf-8")
            self.assertIn("provider_stream_continuation_completed", text)
            self.assertNotIn("provider_stream_continuation_unsupported", text)


if __name__ == "__main__":
    unittest.main()
