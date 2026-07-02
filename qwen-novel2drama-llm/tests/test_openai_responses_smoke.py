from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.openai_responses_smoke import run_smoke


class OpenAIResponsesSmokeTests(unittest.TestCase):
    def test_dry_run_smoke_passes_without_live_credentials(self) -> None:
        report = run_smoke(project_root=PROJECT_ROOT, live=False, base_url="https://api.example/v1")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["mode"], "dry_run")
        self.assertTrue(report["result"]["output"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
