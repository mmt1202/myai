from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.deploy_profile import CLOUD_SPECIALIZATION_TODO, DEPLOY_REQUIREMENTS, deploy_profile


class DeployProfileTests(unittest.TestCase):
    def test_deploy_profile_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = deploy_profile(Path(tmpdir))
            self.assertEqual(report["status"], "failed")
            self.assertGreater(len(report["missing"]), 0)
            self.assertIn("Kubernetes / Terraform", report["cloud_specialization_todo"])

    def test_deploy_profile_passes_when_required_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for paths in DEPLOY_REQUIREMENTS.values():
                for path in paths:
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("ok", encoding="utf-8")
            report = deploy_profile(root)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["missing"], [])
            self.assertEqual(CLOUD_SPECIALIZATION_TODO, report["cloud_specialization_todo"])


if __name__ == "__main__":
    unittest.main()
