from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.quality_gate import discover_case_files, run_quality_gate


class QualityGateTests(unittest.TestCase):
    def test_repo_golden_dataset_passes_gate(self) -> None:
        report = run_quality_gate(PROJECT_ROOT / "evals" / "golden", min_score=0.85)
        self.assertEqual(report["status"], "passed")
        self.assertGreaterEqual(report["total"], 10)
        self.assertGreaterEqual(report["suite_count"], 4)

    def test_gate_fails_below_threshold_or_case_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "cases.json").write_text(json.dumps({"cases": [{"case_id": "bad", "task": "demo", "request": {"actual": {"ok": False}}, "expected": {"ok": True}}]}, ensure_ascii=False), encoding="utf-8")
            report = run_quality_gate(root, min_score=0.85)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failed"], 1)

    def test_discover_case_files(self) -> None:
        files = discover_case_files(PROJECT_ROOT / "evals" / "golden")
        self.assertGreaterEqual(len(files), 4)


if __name__ == "__main__":
    unittest.main()
