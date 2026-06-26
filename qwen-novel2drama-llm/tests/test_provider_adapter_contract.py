from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import chunk_text, normalize_usage, provider_stream_event, response_envelope, text_from_content_blocks, text_from_provider_response
from providers.openai_compatible import OpenAICompatibleProvider


class FakeSSEProviderResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def __iter__(self):
        for line in self.lines:
            yield line.encode("utf-8")


class ProviderAdapterContractTests(unittest.TestCase):
    def test_text_from_content_blocks(self) -> None:
        text = text_from_content_blocks([
            {"type": "text", "text": "hello"},
            {"type": "metadata", "metadata": {"a": 1}},
            {"type": "image", "uri": "file://a.png"},
        ])
        self.assertIn("hello", text)
        self.assertIn("file://a.png", text)

    def test_response_envelope(self) -> None:
        envelope = response_envelope(status="ok", request_id_value="r1", output={"content": []})
        self.assertEqual(envelope["request_id"], "r1")
        self.assertEqual(envelope["status"], "ok")
        self.assertIn("usage", envelope)

    def test_normalize_usage(self) -> None:
        usage = normalize_usage({"prompt_tokens": 2, "completion_tokens": 3})
        self.assertEqual(usage["input_tokens"], 2)
        self.assertEqual(usage["output_tokens"], 3)
        self.assertEqual(usage["total_tokens"], 5)

    def test_provider_stream_event_shape(self) -> None:
        chunk = provider_stream_event("provider_stream_delta", request_id_value="r1", delta="hello", index=0)
        self.assertEqual(chunk["request_id"], "r1")
        self.assertEqual(chunk["event_type"], "provider_stream_delta")
        self.assertEqual(chunk["delta"], "hello")
        self.assertFalse(chunk["done"])
        self.assertIn("chunk_id", chunk)

    def test_text_from_provider_response(self) -> None:
        response = {"output": {"content": [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]}}
        self.assertEqual(text_from_provider_response(response), "hello world")

    def test_chunk_text(self) -> None:
        self.assertEqual(chunk_text("abcdef", chunk_chars=2), ["ab", "cd", "ef"])

    def test_openai_payload_building(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"})
        payload = provider.build_payload({"input": [{"type": "text", "text": "hello"}], "temperature": 0.1, "max_output_tokens": 32})
        self.assertEqual(payload["model"], "demo-model")
        self.assertEqual(payload["temperature"], 0.1)
        self.assertEqual(payload["max_tokens"], 32)
        self.assertEqual(payload["messages"][-1]["content"], "hello")

    def test_openai_stream_payload_building(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"})
        payload = provider.build_payload({"input": [{"type": "text", "text": "hello"}], "stream": True, "stream_include_usage": True})
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["stream_options"], {"include_usage": True})

    def test_openai_dry_run(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        result = provider.generate({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "dry_run": True})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertIn("provider_payload", result["output"])

    def test_openai_dry_run_provider_alias(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        result = provider.generate({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "dry_run_provider": True})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])

    def test_openai_dry_run_stream_uses_native_stream_shape(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        chunks = list(provider.stream_generate({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "dry_run": True}))
        self.assertEqual(chunks[0]["event_type"], "provider_stream_started")
        self.assertEqual(chunks[1]["event_type"], "provider_stream_delta")
        self.assertIn('"stream": true', chunks[1]["delta"])
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(chunks[-1]["done"])

    def test_openai_iter_sse_json(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"})
        events = list(provider.iter_sse_json(FakeSSEProviderResponse([": keepalive\n", "data: {\"a\": 1}\n", "data: [DONE]\n"])))
        self.assertEqual(events, [{"a": 1}])

    def test_openai_native_stream_generate(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        response = FakeSSEProviderResponse(
            [
                'data: {"id":"c1","model":"demo-model","choices":[{"delta":{"content":"hel"},"finish_reason":null}]}\n',
                'data: {"id":"c2","model":"demo-model","choices":[{"delta":{"content":"lo"},"finish_reason":null}]}\n',
                'data: {"id":"c3","model":"demo-model","choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n',
                "data: [DONE]\n",
            ]
        )
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout=120):  # type: ignore[no-untyped-def]
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return response

        with patch("providers.openai_compatible.urllib.request.urlopen", side_effect=fake_urlopen):
            chunks = list(provider.stream_generate({"request_id": "s1", "input": [{"type": "text", "text": "hello"}], "stream_include_usage": True}))
        self.assertTrue(captured["payload"]["stream"])  # type: ignore[index]
        self.assertEqual(chunks[0]["event_type"], "provider_stream_started")
        deltas = [chunk["delta"] for chunk in chunks if chunk["event_type"] == "provider_stream_delta"]
        self.assertEqual(deltas, ["hel", "lo"])
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        self.assertEqual(chunks[-1]["output"]["content"][0]["text"], "hello")
        self.assertEqual(chunks[-1]["usage"]["total_tokens"], 3)
        self.assertEqual(chunks[-1]["output"]["finish_reason"], "stop")

    def test_openai_tool_call_buffer_reconstructs_arguments(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"})
        buffer: dict[int, dict] = {}
        provider.update_tool_call_buffer(buffer, {"index": 0, "id": "call_1", "type": "function", "function": {"name": "foundation."}})
        provider.update_tool_call_buffer(buffer, {"index": 0, "function": {"name": "token_count", "arguments": "{\"request\":"}})
        provider.update_tool_call_buffer(buffer, {"index": 0, "function": {"arguments": "{\"input\":[]}}"}})
        tool_calls = provider.reconstructed_tool_calls(buffer)
        self.assertEqual(tool_calls[0]["id"], "call_1")
        self.assertEqual(tool_calls[0]["function"]["name"], "foundation.token_count")
        self.assertEqual(tool_calls[0]["function"]["arguments"], '{"request":{"input":[]}}')
        self.assertEqual(tool_calls[0]["arguments_json"], {"request": {"input": []}})

    def test_openai_native_stream_reconstructs_tool_calls(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        response = FakeSSEProviderResponse(
            [
                'data: {"id":"tc1","model":"demo-model","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"foundation."}}]},"finish_reason":null}]}\n',
                'data: {"id":"tc2","model":"demo-model","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"token_count","arguments":"{\\\"request\\\":"}}]},"finish_reason":null}]}\n',
                'data: {"id":"tc3","model":"demo-model","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\\"input\\\":[]}}"}}]},"finish_reason":null}]}\n',
                'data: {"id":"tc4","model":"demo-model","choices":[{"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n',
                "data: [DONE]\n",
            ]
        )

        with patch("providers.openai_compatible.urllib.request.urlopen", return_value=response):
            chunks = list(provider.stream_generate({"request_id": "tools1", "input": [{"type": "text", "text": "hello"}], "tools": [{"type": "function", "function": {"name": "foundation.token_count"}}]}))
        tool_delta_chunks = [chunk for chunk in chunks if chunk["event_type"] == "provider_stream_tool_call_delta"]
        self.assertEqual(len(tool_delta_chunks), 3)
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        tool_calls = chunks[-1]["output"]["tool_calls"]
        self.assertEqual(tool_calls[0]["id"], "call_1")
        self.assertEqual(tool_calls[0]["function"]["name"], "foundation.token_count")
        self.assertEqual(tool_calls[0]["function"]["arguments"], '{"request":{"input":[]}}')
        self.assertEqual(tool_calls[0]["arguments_json"], {"request": {"input": []}})
        self.assertEqual(chunks[-1]["output"]["finish_reason"], "tool_calls")
        self.assertEqual(chunks[-1]["metadata"]["tool_call_count"], 1)

    def test_parse_chat_response(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"})
        result = provider.parse_chat_response(
            {"model": "demo-model", "choices": [{"message": {"role": "assistant", "content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
            {"request_id": "r1"},
        )
        self.assertEqual(result["output"]["content"][0]["text"], "hi")
        self.assertEqual(result["usage"]["total_tokens"], 3)


if __name__ == "__main__":
    unittest.main()
