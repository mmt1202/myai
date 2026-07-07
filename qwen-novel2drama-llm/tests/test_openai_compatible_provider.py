from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.factory import build_provider, generate_with_registry, stream_generate_with_registry
from providers.openai_compatible import OpenAICompatibleProvider


MODEL_INSTANCE = {
    "id": "external.deepseek.chat",
    "provider": "deepseek",
    "runtime": "http_chat_completions",
    "model_name": "${DEEPSEEK_MODEL}",
    "runtime_config": {"base_url_env": "DEEPSEEK_BASE_URL", "api_key_env": "DEEPSEEK_API_KEY", "model_name_env": "DEEPSEEK_MODEL"},
    "capabilities": ["text.chat", "tool.calling"],
    "input_modalities": ["text"],
    "output_modalities": ["text"],
}


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_registry_env_config_is_used(self) -> None:
        provider = OpenAICompatibleProvider(MODEL_INSTANCE)
        self.assertEqual(provider.api_key_env, "DEEPSEEK_API_KEY")
        self.assertEqual(provider.base_url_env, "DEEPSEEK_BASE_URL")
        self.assertEqual(provider.model_name_env, "DEEPSEEK_MODEL")

    def test_factory_preserves_registry_specific_api_key_env(self) -> None:
        provider = build_provider(MODEL_INSTANCE)
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key_env, "DEEPSEEK_API_KEY")
        override = build_provider(MODEL_INSTANCE, api_key_env="CUSTOM_KEY")
        self.assertEqual(override.api_key_env, "CUSTOM_KEY")

    def test_payload_supports_common_chat_controls(self) -> None:
        provider = OpenAICompatibleProvider(MODEL_INSTANCE, base_url="https://provider.example/v1")
        payload = provider.build_payload({
            "model": "custom-model",
            "input": [{"type": "text", "text": "hello"}],
            "max_output_tokens": 32,
            "tools": [{"type": "function", "function": {"name": "demo"}}],
            "tool_choice": "auto",
            "top_p": 0.8,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.2,
            "response_format": {"type": "json_object"},
            "seed": 7,
            "metadata": {"trace": "t1"},
        })
        self.assertEqual(payload["model"], "custom-model")
        self.assertEqual(payload["max_tokens"], 32)
        self.assertEqual(payload["tools"][0]["type"], "function")
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertEqual(payload["top_p"], 0.8)
        self.assertEqual(payload["frequency_penalty"], 0.1)
        self.assertEqual(payload["presence_penalty"], 0.2)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["seed"], 7)
        self.assertEqual(payload["metadata"], {"trace": "t1"})

    def test_dry_run_and_stream_work_without_credentials(self) -> None:
        provider = OpenAICompatibleProvider(MODEL_INSTANCE, base_url="https://provider.example/v1")
        result = provider.generate({"dry_run": True, "input": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertEqual(result["output"]["env"]["api_key_env"], "DEEPSEEK_API_KEY")
        events = list(provider.stream_generate({"dry_run": True, "input": [{"type": "text", "text": "hello"}]}))
        self.assertEqual(events[-1]["event_type"], "provider_stream_completed")
        self.assertTrue(events[-1]["output"]["dry_run"])

    def test_missing_external_api_key_fails_before_network(self) -> None:
        old = os.environ.get("DEEPSEEK_API_KEY")
        try:
            os.environ.pop("DEEPSEEK_API_KEY", None)
            provider = OpenAICompatibleProvider(MODEL_INSTANCE, base_url="https://provider.example/v1")
            with self.assertRaises(ProviderError) as ctx:
                provider.generate({"input": [{"type": "text", "text": "hello"}]})
            self.assertEqual(ctx.exception.code, "provider_auth_missing")
            with self.assertRaises(ProviderError) as stream_ctx:
                list(provider.stream_generate({"input": [{"type": "text", "text": "hello"}]}))
            self.assertEqual(stream_ctx.exception.code, "provider_auth_missing")
        finally:
            if old is not None:
                os.environ["DEEPSEEK_API_KEY"] = old

    def test_registry_helpers_generate_and_stream_dry_run(self) -> None:
        registry = {"instances": [MODEL_INSTANCE]}
        result = generate_with_registry({"model_id": "external.deepseek.chat", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="https://provider.example/v1")
        self.assertEqual(result["model"]["provider"], "openai_compatible")
        self.assertEqual(result["output"]["env"]["api_key_env"], "DEEPSEEK_API_KEY")
        events = list(stream_generate_with_registry({"model_id": "external.deepseek.chat", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="https://provider.example/v1"))
        self.assertEqual(events[-1]["event_type"], "provider_stream_completed")


if __name__ == "__main__":
    unittest.main()
