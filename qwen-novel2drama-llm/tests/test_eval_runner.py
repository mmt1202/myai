from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.eval_runner import EvalCase, load_eval_cases, run_eval_cases, score_case


class EvalRunnerTests(unittest.TestCase):
    def test_score_case(self) -> None:
        score = score_case({"status": "ok", "x": 1}, {"status": "ok", "x": 2})
        self.assertFalse(score["passed"])
        self.assertEqual(score["score"], 0.5)

    def test_load_and_run_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cases.json"
            path.write_text('{"cases":[{"case_id":"c1","task":"router_eval","request":{"x":1},"expected":{"x":1}}]}', encoding="utf-8")
            cases = load_eval_cases(path)
            report = run_eval_cases(cases, lambda request: {"x": request["x"]})
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["passed"], 1)


if __name__ == "__main__":
    unittest.main()
