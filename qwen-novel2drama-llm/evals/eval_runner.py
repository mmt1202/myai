from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    task: str
    request: dict[str, Any]
    expected: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_eval_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("cases") if isinstance(raw, dict) else raw
    return [EvalCase(case_id=str(item.get("case_id") or item.get("id")), task=str(item.get("task") or "generic"), request=item.get("request") or {}, expected=item.get("expected") or {}) for item in items]


def score_case(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for key, value in expected.items():
        actual_value = actual.get(key)
        passed = actual_value == value
        checks.append({"key": key, "expected": value, "actual": actual_value, "passed": passed})
    passed_count = sum(1 for item in checks if item["passed"])
    return {"passed": passed_count == len(checks), "score": 1.0 if not checks else passed_count / len(checks), "checks": checks}


def run_eval_cases(cases: list[EvalCase], runner: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        actual = runner(case.request)
        score = score_case(case.expected, actual)
        results.append({"case_id": case.case_id, "task": case.task, "actual": actual, "score": score})
    passed = sum(1 for item in results if item["score"]["passed"])
    return {"status": "passed" if passed == len(results) else "failed", "total": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


def golden_runner(request: dict[str, Any]) -> dict[str, Any]:
    return request.get("actual") or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dependency-free foundation eval cases.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = run_eval_cases(load_eval_cases(Path(args.cases)), golden_runner)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
