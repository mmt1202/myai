from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_PREFIXES = [
    "python -m unittest",
    "python -m pytest",
    "pytest",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_allowed_command(command: str, allowed_prefixes: list[str]) -> bool:
    normalized = " ".join(command.strip().split())
    return any(normalized == prefix or normalized.startswith(prefix + " ") for prefix in allowed_prefixes)


def run_command(command: str, project_root: Path, timeout: int, allowed_prefixes: list[str], dry_run: bool = False) -> dict[str, Any]:
    record: dict[str, Any] = {
        "command": command,
        "allowed": is_allowed_command(command, allowed_prefixes),
        "dry_run": dry_run,
        "status": "pending",
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }
    if not record["allowed"]:
        record["status"] = "skipped"
        record["stderr"] = "command is not allowed by test runner policy"
        return record
    if dry_run:
        record["status"] = "planned"
        return record
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        record["returncode"] = completed.returncode
        record["stdout"] = completed.stdout
        record["stderr"] = completed.stderr
        record["status"] = "passed" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        record["status"] = "timeout"
        record["stdout"] = exc.stdout or ""
        record["stderr"] = exc.stderr or ""
    return record


def run_test_plan(plan: dict[str, Any], project_root: Path, timeout: int, allowed_prefixes: list[str], dry_run: bool = False) -> dict[str, Any]:
    commands = list(dict.fromkeys(plan.get("tests_to_run", [])))
    results = [run_command(command, project_root, timeout, allowed_prefixes, dry_run) for command in commands]
    passed = sum(1 for item in results if item["status"] == "passed")
    failed = sum(1 for item in results if item["status"] == "failed")
    skipped = sum(1 for item in results if item["status"] == "skipped")
    timeout_count = sum(1 for item in results if item["status"] == "timeout")
    planned = sum(1 for item in results if item["status"] == "planned")
    if failed or timeout_count:
        overall = "failed"
    elif skipped and not passed and not planned:
        overall = "skipped"
    elif planned:
        overall = "planned"
    else:
        overall = "passed"
    return {
        "task": plan.get("task"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "timeout": timeout_count,
            "planned": planned,
        },
        "results": results,
    }


def default_output_path(project_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return project_root / "outputs" / "test_runs" / f"test_run_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--plan", default="outputs/patch_plan.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-prefix", action="append", default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    plan = load_json(project_root / args.plan)
    allowed_prefixes = args.allow_prefix or DEFAULT_ALLOWED_PREFIXES
    report = run_test_plan(plan, project_root, args.timeout, allowed_prefixes, args.dry_run)
    output_path = project_root / args.output if args.output else default_output_path(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"test run report written: {output_path}")
    return 0 if report["overall_status"] in {"passed", "planned", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
