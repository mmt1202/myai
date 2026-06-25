from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from create_unified_diff import apply_change, safe_project_path, unified_diff_for_file

CONFIRM_TOKEN = "APPLY"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_patch_spec(project_root: Path, patch_spec: dict[str, Any], dry_run: bool = True, confirm: str | None = None) -> dict[str, Any]:
    if not dry_run and confirm != CONFIRM_TOKEN:
        raise PermissionError(f"refusing to write files without --confirm {CONFIRM_TOKEN}")

    results: list[dict[str, Any]] = []
    for change in patch_spec.get("changes", []):
        rel_path = str(change["path"])
        path = safe_project_path(project_root, rel_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"file not found: {rel_path}")

        old_text = path.read_text(encoding="utf-8")
        new_text, operation = apply_change(old_text, change)
        diff_text = unified_diff_for_file(path, old_text, new_text, rel_path)
        changed = old_text != new_text

        if changed and not dry_run:
            path.write_text(new_text, encoding="utf-8")

        results.append(
            {
                "path": rel_path,
                "operation": operation,
                "changed": changed,
                "dry_run": dry_run,
                "old_chars": len(old_text),
                "new_chars": len(new_text),
                "diff_preview": diff_text,
            }
        )

    changed_count = sum(1 for item in results if item["changed"])
    return {
        "task": patch_spec.get("task"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "changed_file_count": changed_count,
        "results": results,
    }


def default_report_path(project_root: Path, dry_run: bool) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "dry_run" if dry_run else "applied"
    return project_root / "outputs" / "patch_apply" / f"patch_apply_{suffix}_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--report", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    patch_spec = load_json(project_root / args.spec)
    dry_run = args.dry_run or args.confirm != CONFIRM_TOKEN
    report = apply_patch_spec(project_root, patch_spec, dry_run=dry_run, confirm=args.confirm)

    report_path = project_root / args.report if args.report else default_report_path(project_root, dry_run)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patch apply report written: {report_path}")
    if dry_run:
        print(f"dry-run only; pass --confirm {CONFIRM_TOKEN} to write files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
