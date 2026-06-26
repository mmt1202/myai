from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import chunk_text, normalize_usage, provider_stream_event, response_envelope, text_from_content_blocks, text_from_provider_response
from providers.openai_compatible import OpenAICompatibleProvider


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

    def test_openai_dry_run(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        result = provider.generate({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "dry_run": True})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertIn("provider_payload", result["output"])

    def test_openai_dry_run_stream_falls_back_to_full_response_chunk(self) -> None:
        provider = OpenAICompatibleProvider({"id": "m1", "model_name": "demo-model"}, base_url="http://example.test/v1")
        chunks = list(provider.stream_generate({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "dry_run": True}))
        self.assertEqual(chunks[0]["event_type"], "provider_stream_started")
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(chunks[-1]["done"])

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
