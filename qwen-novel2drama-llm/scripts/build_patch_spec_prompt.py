from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from read_context_chunk import read_chunk


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def target_chunks(project_root: Path, patch_plan: dict[str, Any], max_files: int, chunk_chars: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for item in patch_plan.get("target_files", [])[:max_files]:
        path = item.get("path")
        if not path:
            continue
        try:
            chunk = read_chunk(project_root, str(path), chunk_id=0, chunk_chars=chunk_chars)
        except Exception as exc:  # noqa: BLE001
            chunk = {"path": path, "error": str(exc)}
        chunks.append(chunk)
    return chunks


def build_prompt_payload(
    task: str,
    workflow_manifest: dict[str, Any],
    patch_plan: dict[str, Any],
    schema: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "role": "coding_patch_spec_generator",
        "instruction": "Generate a patch_spec_v1 JSON object only. Do not generate markdown. Do not edit files directly.",
        "task": task,
        "schema": schema,
        "workflow_summary": workflow_manifest.get("summary", {}),
        "patch_plan": {
            "target_files": patch_plan.get("target_files", []),
            "related_symbols": patch_plan.get("related_symbols", []),
            "steps": patch_plan.get("steps", []),
            "safety_rules": patch_plan.get("safety_rules", []),
        },
        "file_chunks": chunks,
        "output_contract": {
            "format": "json_only",
            "schema_name": "patch_spec_v1",
            "must_include": ["task", "changes"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--patch-plan", required=True)
    parser.add_argument("--schema", default="configs/patch_spec_schema.json")
    parser.add_argument("--output", default="outputs/model_prompts/patch_spec_prompt.json")
    parser.add_argument("--max-files", type=int, default=5)
    parser.add_argument("--chunk-chars", type=int, default=3000)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    workflow = load_json(project_root / args.workflow)
    patch_plan = load_json(project_root / args.patch_plan)
    schema = load_json(project_root / args.schema)
    task = str(patch_plan.get("task") or workflow.get("task") or "")
    chunks = target_chunks(project_root, patch_plan, args.max_files, args.chunk_chars)
    payload = build_prompt_payload(task, workflow, patch_plan, schema, chunks)

    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patch spec prompt written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
