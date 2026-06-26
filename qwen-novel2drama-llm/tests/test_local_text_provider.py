from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.local_text import LocalTextProvider


class LocalTextProviderTests(unittest.TestCase):
    def test_build_prompt_from_content_blocks(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"})
        prompt = provider.build_prompt({"input": [{"type": "text", "text": "hello"}, {"type": "metadata", "metadata": {"a": 1}}]})
        self.assertIn("hello", prompt)
        self.assertIn("\"a\": 1", prompt)

    def test_dry_run_does_not_require_model_path(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers", "model_name": "demo"})
        result = provider.generate({"request_id": "r1", "dry_run": True, "input": [{"type": "text", "text": "hello"}], "max_output_tokens": 16})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["output"]["dry_run"])
        self.assertIn("dry_run_no_local_model_load", result["warnings"])

    def test_missing_model_path_fails_for_real_execution(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"})
        with self.assertRaises(ProviderError):
            provider.generate({"input": [{"type": "text", "text": "hello"}]})

    def test_request_model_path_overrides_provider_model_path(self) -> None:
        provider = LocalTextProvider({"id": "local1", "provider": "local", "runtime": "transformers"}, model_path="/a")
        model_path, _, _ = provider.resolved_paths({"model_path": "/b"})
        self.assertEqual(model_path, "/b")


if __name__ == "__main__":
    unittest.main()
