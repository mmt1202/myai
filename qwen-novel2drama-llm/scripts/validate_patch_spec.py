from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_paths_from_plan(plan: dict[str, Any]) -> set[str]:
    return {str(item.get("path")) for item in plan.get("target_files", []) if item.get("path")}


def validate_patch_spec(spec: dict[str, Any], plan: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec.get("task"), str) or not spec.get("task"):
        errors.append("task must be a non-empty string")
    changes = spec.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("changes must be a non-empty list")
        return errors

    allowed_paths = allowed_paths_from_plan(plan or {}) if plan else set()
    for index, change in enumerate(changes):
        prefix = f"changes[{index}]"
        path = change.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"{prefix}.path must be a non-empty string")
            continue
        if path.startswith("/") or ".." in Path(path).parts:
            errors.append(f"{prefix}.path must stay inside project root")
        if allowed_paths and path not in allowed_paths:
            errors.append(f"{prefix}.path is not listed in patch plan target_files")

        has_replace = "find" in change or "replace" in change
        has_append = "append" in change
        if has_replace and has_append:
            errors.append(f"{prefix} cannot combine replace and append")
        elif has_replace:
            if not isinstance(change.get("find"), str) or change.get("find") == "":
                errors.append(f"{prefix}.find must be a non-empty string")
            if not isinstance(change.get("replace"), str):
                errors.append(f"{prefix}.replace must be a string")
            if "count" not in change:
                errors.append(f"{prefix}.count is required for replace")
            elif not isinstance(change.get("count"), int) or change.get("count") < 1:
                errors.append(f"{prefix}.count must be a positive integer")
        elif has_append:
            if not isinstance(change.get("append"), str) or change.get("append") == "":
                errors.append(f"{prefix}.append must be a non-empty string")
        else:
            errors.append(f"{prefix} must use replace or append")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--patch-plan", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    spec = load_json(Path(args.spec))
    plan = load_json(Path(args.patch_plan)) if args.patch_plan else None
    errors = validate_patch_spec(spec, plan)
    report = {"valid": not errors, "errors": errors}
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
