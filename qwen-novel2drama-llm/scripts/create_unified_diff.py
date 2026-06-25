from __future__ import annotations

import argparse
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_project_path(project_root: Path, rel_path: str) -> Path:
    path = (project_root / rel_path).resolve()
    if not path.is_relative_to(project_root):
        raise ValueError(f"path is outside project root: {rel_path}")
    return path


def replace_exact(text: str, find: str, replace: str, count: int | None) -> tuple[str, int]:
    occurrences = text.count(find)
    if occurrences == 0:
        raise ValueError("find text was not found")
    if count is not None and occurrences != count:
        raise ValueError(f"expected {count} occurrences but found {occurrences}")
    return text.replace(find, replace, count or -1), occurrences


def apply_change(text: str, change: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "find" in change and "replace" in change:
        new_text, occurrences = replace_exact(text, str(change["find"]), str(change["replace"]), change.get("count"))
        return new_text, {"operation": "replace", "occurrences": occurrences}
    if "append" in change:
        append_text = str(change["append"])
        separator = "" if text.endswith("\n") or not text else "\n"
        return text + separator + append_text, {"operation": "append", "occurrences": 1}
    raise ValueError("unsupported change operation; use find/replace or append")


def unified_diff_for_file(path: Path, old_text: str, new_text: str, rel_path: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="",
        )
    )


def create_diff(project_root: Path, patch_spec: dict[str, Any]) -> dict[str, Any]:
    file_diffs: list[dict[str, Any]] = []
    combined_diff_parts: list[str] = []
    for change in patch_spec.get("changes", []):
        rel_path = str(change["path"])
        path = safe_project_path(project_root, rel_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"file not found: {rel_path}")
        old_text = path.read_text(encoding="utf-8")
        new_text, operation = apply_change(old_text, change)
        diff_text = unified_diff_for_file(path, old_text, new_text, rel_path)
        file_diffs.append(
            {
                "path": rel_path,
                "operation": operation,
                "changed": old_text != new_text,
                "old_chars": len(old_text),
                "new_chars": len(new_text),
            }
        )
        if diff_text:
            combined_diff_parts.append(diff_text)
    return {
        "task": patch_spec.get("task"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "changed_files": file_diffs,
        "diff": "\n".join(combined_diff_parts),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", default="outputs/patches/generated.diff")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    spec_path = project_root / args.spec
    patch_spec = load_json(spec_path)
    result = create_diff(project_root, patch_spec)
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result["diff"], encoding="utf-8")
    if args.report:
        report_path = project_root / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"unified diff written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
