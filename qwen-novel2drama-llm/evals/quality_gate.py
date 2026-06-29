from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals.eval_runner import EvalCase, load_eval_cases, run_eval_cases


def discover_case_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def suite_runner(request: dict[str, Any]) -> dict[str, Any]:
    return request.get("actual") or {}


def run_quality_gate(root: Path, *, min_score: float = 0.85) -> dict[str, Any]:
    files = discover_case_files(root)
    suites: list[dict[str, Any]] = []
    total = 0
    passed = 0
    score_sum = 0.0
    for path in files:
        cases = load_eval_cases(path)
        report = run_eval_cases(cases, suite_runner)
        suite_score = 1.0 if report["total"] == 0 else sum(item["score"]["score"] for item in report["results"]) / report["total"]
        suites.append({"suite": str(path.relative_to(root)), "status": report["status"], "total": report["total"], "passed": report["passed"], "failed": report["failed"], "score": round(suite_score, 6), "results": report["results"]})
        total += report["total"]
        passed += report["passed"]
        score_sum += sum(item["score"]["score"] for item in report["results"])
    overall_score = 1.0 if total == 0 else score_sum / total
    status = "passed" if total > 0 and overall_score >= min_score and all(suite["status"] == "passed" for suite in suites) else "failed"
    return {"status": status, "min_score": min_score, "score": round(overall_score, 6), "total": total, "passed": passed, "failed": total - passed, "suite_count": len(suites), "suites": suites}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden dataset quality gate.")
    parser.add_argument("--root", default="evals/golden")
    parser.add_argument("--min-score", type=float, default=0.85)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = run_quality_gate(Path(args.root), min_score=args.min_score)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
