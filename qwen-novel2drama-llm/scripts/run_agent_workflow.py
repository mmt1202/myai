from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_code_symbols import build_symbol_index
from build_context_index import build_index
from create_patch_plan import create_patch_plan
from run_test_plan import DEFAULT_ALLOWED_PREFIXES, run_test_plan


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_agent_workflow(
    project_root: Path,
    task: str,
    output_dir: Path,
    profile: str = "configs/context_profile.json",
    execute_tests: bool = False,
    timeout: int = 120,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    context_index = build_index(project_root, project_root / profile)
    context_path = output_dir / "context_index.json"
    write_json(context_path, context_index)

    symbol_index = build_symbol_index(project_root, context_path)
    symbols_path = output_dir / "code_symbols.json"
    write_json(symbols_path, symbol_index)

    patch_plan = create_patch_plan(task, context_index, symbol_index)
    patch_plan_path = output_dir / "patch_plan.json"
    write_json(patch_plan_path, patch_plan)

    test_report = run_test_plan(
        patch_plan,
        project_root,
        timeout=timeout,
        allowed_prefixes=DEFAULT_ALLOWED_PREFIXES,
        dry_run=not execute_tests,
    )
    test_report_path = output_dir / "test_plan_report.json"
    write_json(test_report_path, test_report)

    manifest = {
        "task": task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execute_tests": execute_tests,
        "artifacts": {
            "context_index": str(context_path.relative_to(project_root)),
            "code_symbols": str(symbols_path.relative_to(project_root)),
            "patch_plan": str(patch_plan_path.relative_to(project_root)),
            "test_plan_report": str(test_report_path.relative_to(project_root)),
        },
        "summary": {
            "context_file_count": context_index.get("file_count"),
            "symbol_file_count": symbol_index.get("file_count"),
            "target_file_count": len(patch_plan.get("target_files", [])),
            "related_symbol_count": len(patch_plan.get("related_symbols", [])),
            "test_status": test_report.get("overall_status"),
        },
        "next_steps": [
            "Review the patch plan and selected target files.",
            "Read relevant chunks before writing a patch spec.",
            "Generate a unified diff from a reviewed patch spec.",
            "Dry-run the safe patch applier before writing files.",
            "Run tests after applying a confirmed patch.",
        ],
    }
    manifest_path = output_dir / "workflow_manifest.json"
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--profile", default="configs/context_profile.json")
    parser.add_argument("--execute-tests", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    output_dir = project_root / args.output_dir if args.output_dir else project_root / "outputs" / "agent_runs" / timestamp()
    manifest = run_agent_workflow(project_root, args.task, output_dir, args.profile, args.execute_tests, args.timeout)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["summary"].get("test_status") in {"passed", "planned", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
