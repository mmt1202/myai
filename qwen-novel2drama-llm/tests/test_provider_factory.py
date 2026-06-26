from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.factory import build_provider, find_model_instance, generate_with_registry
from providers.openai_compatible import OpenAICompatibleProvider


class ProviderFactoryTests(unittest.TestCase):
    def test_find_model_instance_by_id_and_alias(self) -> None:
        registry = {"instances": [{"id": "m1", "aliases": ["smart"], "provider": "openai_compatible", "runtime": "http_chat_completions"}]}
        self.assertEqual(find_model_instance(registry, "m1")["id"], "m1")
        self.assertEqual(find_model_instance(registry, "smart")["id"], "m1")

    def test_build_openai_compatible_provider(self) -> None:
        provider = build_provider({"id": "m1", "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"})
        self.assertIsInstance(provider, OpenAICompatibleProvider)

    def test_generate_with_registry_dry_run(self) -> None:
        registry = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
        result = generate_with_registry({"model_id": "m1", "dry_run": True, "input": [{"type": "text", "text": "hello"}]}, registry, base_url="http://example.test/v1")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
