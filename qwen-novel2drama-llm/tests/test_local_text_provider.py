from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.local_text import LocalTextProvider, cache_stats, clear_model_cache, local_cache_key


class LocalTextProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_model_cache()

    def tearDown(self) -> None:
        clear_model_cache()

    def test_build_prompt_from_content_blocks(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"})
        prompt = provider.build_prompt({"input": [{"type": "text", "text": "hello"}, {"type": "metadata", "metadata": {"a": 1}}]})
        self.assertIn("hello", prompt)
        self.assertIn('"a": 1', prompt)

    def test_dry_run_does_not_require_model_path(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers", "model_name": "demo"})
        result = provider.generate({"request_id": "r1", "dry_run": True, "input": [{"type": "text", "text": "hello"}], "max_output_tokens": 16})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertIn("dry_run_no_local_model_load", result["warnings"])

    def test_dry_run_stream_outputs_standard_chunks(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers", "model_name": "demo"})
        chunks = list(provider.stream_generate({"request_id": "r1", "dry_run": True, "input": [{"type": "text", "text": "hello"}], "stream_chunk_chars": 2}))
        self.assertEqual(chunks[0]["event_type"], "provider_stream_started")
        self.assertTrue(any(chunk["event_type"] == "provider_stream_delta" for chunk in chunks))
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(chunks[-1]["done"])

    def test_missing_model_path_fails_for_real_execution(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"})
        with self.assertRaises(ProviderError):
            provider.generate({"input": [{"type": "text", "text": "hello"}]})

    def test_request_model_path_overrides_provider_model_path(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/a")
        model_path, _, _ = provider.resolved_paths({"model_path": "/b"})
        self.assertEqual(model_path, "/b")

    def test_cache_key(self) -> None:
        self.assertEqual(local_cache_key("/m", None), ("/m", None))
        self.assertEqual(local_cache_key("/m", "/a"), ("/m", "/a"))

    def test_health_includes_cache_and_streaming_state(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m")
        health = provider.health()
        self.assertTrue(health["model_path_configured"])
        self.assertTrue(health["streaming"])
        self.assertIn("cache", health)

    def test_cached_runtime_loads_once(self) -> None:
        calls = {"load": 0, "generate": 0}

        def fake_load_model(model_path: str, adapter_path: str | None = None):
            calls["load"] += 1
            return "tokenizer", "model", {"model_path": model_path, "adapter_path": adapter_path}

        def fake_generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt):
            calls["generate"] += 1
            return f"generated:{prompt}"

        fake_module = SimpleNamespace(load_model=fake_load_model, generate_text=fake_generate_text, load_system_prompt=lambda path=None: "system")
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m")
        with patch("providers.local_text.importlib.import_module", return_value=fake_module):
            first = provider.generate({"input": [{"type": "text", "text": "hello"}], "max_output_tokens": 8})
            second = provider.generate({"input": [{"type": "text", "text": "world"}], "max_output_tokens": 8})
        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(calls["load"], 1)
        self.assertEqual(calls["generate"], 2)
        stats = cache_stats()
        self.assertEqual(stats["entry_count"], 1)
        self.assertEqual(stats["entries"][0]["hit_count"], 1)
        self.assertEqual(stats["entries"][0]["generation_count"], 2)

    def test_stream_generate_uses_generate_text_stream_when_available(self) -> None:
        calls = {"load": 0, "stream": 0}

        def fake_load_model(model_path: str, adapter_path: str | None = None):
            calls["load"] += 1
            return "tokenizer", "model", {}

        def fake_generate_text_stream(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt):
            calls["stream"] += 1
            yield "hel"
            yield "lo"

        fake_module = SimpleNamespace(load_model=fake_load_model, generate_text_stream=fake_generate_text_stream, generate_text=lambda *args: "fallback", load_system_prompt=lambda path=None: "system")
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m")
        with patch("providers.local_text.importlib.import_module", return_value=fake_module):
            chunks = list(provider.stream_generate({"request_id": "s1", "input": [{"type": "text", "text": "hello"}], "max_output_tokens": 8}))
        self.assertEqual(calls["load"], 1)
        self.assertEqual(calls["stream"], 1)
        deltas = [chunk["delta"] for chunk in chunks if chunk["event_type"] == "provider_stream_delta"]
        self.assertEqual(deltas, ["hel", "lo"])
        self.assertEqual(chunks[-1]["event_type"], "provider_stream_completed")
        self.assertEqual(cache_stats()["entries"][0]["stream_generation_count"], 1)

    def test_stream_generate_falls_back_to_chunked_generate_text(self) -> None:
        calls = {"load": 0, "generate": 0}

        def fake_load_model(model_path: str, adapter_path: str | None = None):
            calls["load"] += 1
            return "tokenizer", "model", {}

        def fake_generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt):
            calls["generate"] += 1
            return "abcdef"

        fake_module = SimpleNamespace(load_model=fake_load_model, generate_text=fake_generate_text, load_system_prompt=lambda path=None: "system")
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m")
        with patch("providers.local_text.importlib.import_module", return_value=fake_module):
            chunks = list(provider.stream_generate({"request_id": "s1", "input": [{"type": "text", "text": "hello"}], "max_output_tokens": 8, "stream_chunk_chars": 2}))
        self.assertEqual(calls["generate"], 1)
        deltas = [chunk["delta"] for chunk in chunks if chunk["event_type"] == "provider_stream_delta"]
        self.assertEqual(deltas, ["ab", "cd", "ef"])
        self.assertEqual(chunks[-1]["output"]["content"][0]["text"], "abcdef")

    def test_disable_cache_loads_each_time(self) -> None:
        calls = {"load": 0}

        def fake_load_model(model_path: str, adapter_path: str | None = None):
            calls["load"] += 1
            return "tokenizer", "model", {}

        fake_module = SimpleNamespace(load_model=fake_load_model, generate_text=lambda *args: "generated", load_system_prompt=lambda path=None: "system")
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m", use_cache=False)
        with patch("providers.local_text.importlib.import_module", return_value=fake_module):
            provider.generate({"input": [{"type": "text", "text": "hello"}], "max_output_tokens": 8})
            provider.generate({"input": [{"type": "text", "text": "world"}], "max_output_tokens": 8})
        self.assertEqual(calls["load"], 2)
        self.assertEqual(cache_stats()["entry_count"], 0)

    def test_clear_model_cache(self) -> None:
        calls = {"load": 0}

        def fake_load_model(model_path: str, adapter_path: str | None = None):
            calls["load"] += 1
            return "tokenizer", "model", {}

        fake_module = SimpleNamespace(load_model=fake_load_model, generate_text=lambda *args: "generated", load_system_prompt=lambda path=None: "system")
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/m")
        with patch("providers.local_text.importlib.import_module", return_value=fake_module):
            provider.generate({"input": [{"type": "text", "text": "hello"}], "max_output_tokens": 8})
        self.assertEqual(cache_stats()["entry_count"], 1)
        clear_model_cache()
        self.assertEqual(cache_stats()["entry_count"], 0)


if __name__ == "__main__":
    unittest.main()
