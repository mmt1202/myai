from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.provider_candidate_smoke import run_smoke


class ProviderCandidateSmokeTests(unittest.TestCase):
    def test_deepseek_dry_run_smoke(self) -> None:
        report = run_smoke(project_root=PROJECT_ROOT, model_id="external.deepseek.chat", live=False, base_url="https://provider.example/v1")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["env"]["api_key_env"], "DEEPSEEK_API_KEY")
        self.assertTrue(report["result"]["output"]["dry_run"])

    def test_qwen_dry_run_stream_smoke(self) -> None:
        report = run_smoke(project_root=PROJECT_ROOT, model_id="external.qwen_dashscope.omni", live=False, stream=True, base_url="https://provider.example/v1")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["mode"], "dry_run_stream")
        self.assertEqual(report["env"]["api_key_env"], "DASHSCOPE_API_KEY")
        self.assertEqual(report["result"][-1]["event_type"], "provider_stream_completed")

    def test_live_smoke_skips_when_key_missing(self) -> None:
        report = run_smoke(project_root=PROJECT_ROOT, model_id="external.deepseek.chat", live=True, base_url="https://provider.example/v1")
        if report["status"] == "skipped":
            self.assertEqual(report["reason"], "api_key_missing")
        else:
            self.assertIn(report["status"], {"passed", "failed"})


if __name__ == "__main__":
    unittest.main()
