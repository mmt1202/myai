from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apply_patch_spec import CONFIRM_TOKEN, apply_patch_spec
from build_patch_spec_prompt import build_prompt_payload, target_chunks
from call_model_for_patch_spec import call_model
from create_unified_diff import create_diff
from run_agent_workflow import run_agent_workflow, timestamp, write_json
from run_test_plan import DEFAULT_ALLOWED_PREFIXES, run_test_plan
from validate_patch_spec import validate_patch_spec


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_prompt_artifact(project_root: Path, output_dir: Path, workflow_manifest: dict[str, Any], patch_plan: dict[str, Any], max_files: int, chunk_chars: int) -> tuple[Path, dict[str, Any]]:
    schema = load_json(project_root / "configs" / "patch_spec_schema.json")
    chunks = target_chunks(project_root, patch_plan, max_files=max_files, chunk_chars=chunk_chars)
    payload = build_prompt_payload(
        task=str(patch_plan.get("task") or workflow_manifest.get("task") or ""),
        workflow_manifest=workflow_manifest,
        patch_plan=patch_plan,
        schema=schema,
        chunks=chunks,
    )
    prompt_path = output_dir / "patch_spec_prompt.json"
    save_json(prompt_path, payload)
    return prompt_path, payload


def run_ai_code_agent(
    project_root: Path,
    task: str,
    output_dir: Path,
    model_url: str | None = None,
    model_mode: str = "openai_compatible",
    model_name: str = "local-model",
    api_key_env: str = "MODEL_API_KEY",
    temperature: float = 0.0,
    timeout: int = 120,
    patch_spec_path: Path | None = None,
    apply_changes: bool = False,
    execute_tests: bool = False,
    max_files: int = 5,
    chunk_chars: int = 3000,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    workflow_manifest = run_agent_workflow(
        project_root=project_root,
        task=task,
        output_dir=output_dir,
        execute_tests=False,
        timeout=timeout,
    )
    workflow_path = output_dir / "workflow_manifest.json"
    patch_plan_path = output_dir / "patch_plan.json"
    patch_plan = load_json(patch_plan_path)

    prompt_path, prompt_payload = build_prompt_artifact(
        project_root,
        output_dir,
        workflow_manifest,
        patch_plan,
        max_files=max_files,
        chunk_chars=chunk_chars,
    )

    patch_spec: dict[str, Any] | None = None
    model_status = "not_requested"
    model_error: str | None = None
    final_patch_spec_path = output_dir / "patch_spec.json"

    if patch_spec_path:
        patch_spec = load_json(patch_spec_path)
        save_json(final_patch_spec_path, patch_spec)
        model_status = "provided_patch_spec"
    elif model_url:
        try:
            patch_spec = call_model(
                prompt_payload=prompt_payload,
                mode=model_mode,
                url=model_url,
                model=model_name,
                api_key=os.environ.get(api_key_env),
                temperature=temperature,
                timeout=timeout,
            )
            save_json(final_patch_spec_path, patch_spec)
            model_status = "generated_patch_spec"
        except Exception as exc:  # noqa: BLE001
            model_status = "failed"
            model_error = str(exc)

    validation_report: dict[str, Any] | None = None
    diff_report: dict[str, Any] | None = None
    apply_report: dict[str, Any] | None = None
    test_report: dict[str, Any] | None = None

    if patch_spec is not None:
        validation_errors = validate_patch_spec(patch_spec, patch_plan)
        validation_report = {"valid": not validation_errors, "errors": validation_errors}
        save_json(output_dir / "patch_spec_validation.json", validation_report)

        if validation_report["valid"]:
            diff_report = create_diff(project_root, patch_spec)
            save_json(output_dir / "diff_report.json", diff_report)
            diff_path = output_dir / "generated.diff"
            diff_path.write_text(diff_report.get("diff", ""), encoding="utf-8")

            apply_report = apply_patch_spec(
                project_root,
                patch_spec,
                dry_run=not apply_changes,
                confirm=CONFIRM_TOKEN if apply_changes else None,
            )
            save_json(output_dir / ("patch_apply_applied.json" if apply_changes else "patch_apply_dry_run.json"), apply_report)

            test_report = run_test_plan(
                patch_plan,
                project_root,
                timeout=timeout,
                allowed_prefixes=DEFAULT_ALLOWED_PREFIXES,
                dry_run=not execute_tests,
            )
            save_json(output_dir / "test_report.json", test_report)

    report = {
        "task": task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "safe_defaults": {
            "apply_changes": apply_changes,
            "execute_tests": execute_tests,
        },
        "model": {
            "status": model_status,
            "mode": model_mode,
            "model": model_name,
            "url": model_url,
            "error": model_error,
        },
        "artifacts": {
            "workflow_manifest": rel(project_root, workflow_path),
            "patch_plan": rel(project_root, patch_plan_path),
            "patch_spec_prompt": rel(project_root, prompt_path),
            "patch_spec": rel(project_root, final_patch_spec_path) if patch_spec is not None else None,
            "validation": rel(project_root, output_dir / "patch_spec_validation.json") if validation_report else None,
            "diff_report": rel(project_root, output_dir / "diff_report.json") if diff_report else None,
            "diff": rel(project_root, output_dir / "generated.diff") if diff_report else None,
            "apply_report": rel(project_root, output_dir / ("patch_apply_applied.json" if apply_changes else "patch_apply_dry_run.json")) if apply_report else None,
            "test_report": rel(project_root, output_dir / "test_report.json") if test_report else None,
        },
        "status": {
            "workflow": "completed",
            "patch_spec_validation": validation_report,
            "test_status": test_report.get("overall_status") if test_report else None,
        },
        "next_steps": [
            "Review patch_plan.json and patch_spec_prompt.json.",
            "If no model URL was provided, call the model later or provide --patch-spec.",
            "If validation passed, review generated.diff before applying changes.",
            "Use --apply to write changes only after reviewing dry-run artifacts.",
            "Use --execute-tests to run tests after applying a confirmed patch.",
        ],
    }
    save_json(output_dir / "ai_code_agent_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model-url", default=None)
    parser.add_argument("--model-mode", choices=["openai_compatible", "local_generate"], default="openai_compatible")
    parser.add_argument("--model", default="local-model")
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--patch-spec", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--execute-tests", action="store_true")
    parser.add_argument("--max-files", type=int, default=5)
    parser.add_argument("--chunk-chars", type=int, default=3000)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    output_dir = project_root / args.output_dir if args.output_dir else project_root / "outputs" / "ai_code_agent_runs" / timestamp()
    report = run_ai_code_agent(
        project_root=project_root,
        task=args.task,
        output_dir=output_dir,
        model_url=args.model_url,
        model_mode=args.model_mode,
        model_name=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        timeout=args.timeout,
        patch_spec_path=Path(args.patch_spec).resolve() if args.patch_spec else None,
        apply_changes=args.apply,
        execute_tests=args.execute_tests,
        max_files=args.max_files,
        chunk_chars=args.chunk_chars,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    validation = report["status"].get("patch_spec_validation")
    if validation and not validation.get("valid"):
        return 1
    if report["model"].get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
