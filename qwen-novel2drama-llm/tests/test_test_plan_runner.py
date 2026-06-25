from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_test_plan import is_allowed_command, run_command, run_test_plan  # noqa: E402


class TestPlanRunnerTests(unittest.TestCase):
    def test_allowed_command_policy(self) -> None:
        allowed = ["python -m unittest"]
        self.assertTrue(is_allowed_command("python -m unittest discover tests", allowed))
        self.assertFalse(is_allowed_command("rm -rf outputs", allowed))

    def test_run_command_skips_disallowed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command("echo bad", Path(tmpdir), timeout=5, allowed_prefixes=["python -m unittest"])
            self.assertEqual(result["status"], "skipped")
            self.assertFalse(result["allowed"])

    def test_run_test_plan_dry_run(self) -> None:
        plan = {"task": "demo", "tests_to_run": ["python -m unittest discover tests"]}
        report = run_test_plan(plan, PROJECT_ROOT, timeout=5, allowed_prefixes=["python -m unittest"], dry_run=True)
        self.assertEqual(report["overall_status"], "planned")
        self.assertEqual(report["summary"]["planned"], 1)


if __name__ == "__main__":
    unittest.main()
