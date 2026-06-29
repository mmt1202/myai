from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.production_preflight import REQUIRED_FILES, REQUIRED_FLAGS, preflight


class ProductionPreflightTests(unittest.TestCase):
    def test_preflight_reports_missing_files_and_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir(parents=True)
            (root / "docs" / "implementation_status.md").write_text("", encoding="utf-8")
            report = preflight(root)
            self.assertEqual(report["status"], "failed")
            self.assertGreaterEqual(len(report["missing_files"]), len(REQUIRED_FILES) - 1)
            self.assertGreaterEqual(len(report["missing_flags"]), len(REQUIRED_FLAGS))

    def test_preflight_accepts_placeholder_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for path in REQUIRED_FILES:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("placeholder", encoding="utf-8")
            status_path = root / "docs" / "implementation_status.md"
            status_path.write_text("\n".join(REQUIRED_FLAGS), encoding="utf-8")
            env_path = root / "configs" / "deploy" / "production.example.env"
            env_path.write_text("MODEL_API_KEY=<configured outside git>\nFOUNDATION_AGENT_RUN_POSTGRES_DSN=<configured outside git>\n", encoding="utf-8")
            report = preflight(root)
            self.assertEqual(report["unsafe_env_values"], [])
            self.assertEqual(report["status"], "ok")


if __name__ == "__main__":
    unittest.main()
