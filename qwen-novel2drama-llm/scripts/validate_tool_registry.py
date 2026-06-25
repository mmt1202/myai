from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TOOL_FIELDS = {
    "id",
    "name",
    "script",
    "category",
    "write_files",
    "safe_by_default",
    "inputs",
    "outputs",
    "description",
}


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_tool_registry(registry: dict[str, Any], project_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    tools = registry.get("tools")
    if not isinstance(tools, list) or not tools:
        return ["tools must be a non-empty list"]

    seen_ids: set[str] = set()
    for index, tool in enumerate(tools):
        prefix = f"tools[{index}]"
        missing = REQUIRED_TOOL_FIELDS - set(tool.keys())
        for field in sorted(missing):
            errors.append(f"{prefix}.{field} is required")
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or not tool_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif tool_id in seen_ids:
            errors.append(f"{prefix}.id is duplicated: {tool_id}")
        else:
            seen_ids.add(tool_id)

        script = tool.get("script")
        if not isinstance(script, str) or not script.endswith(".py"):
            errors.append(f"{prefix}.script must point to a Python script")
        elif project_root is not None and not (project_root / script).exists():
            errors.append(f"{prefix}.script does not exist: {script}")

        if not isinstance(tool.get("inputs"), list):
            errors.append(f"{prefix}.inputs must be a list")
        if not isinstance(tool.get("outputs"), list):
            errors.append(f"{prefix}.outputs must be a list")
        if tool.get("write_files") is True and tool.get("safe_by_default") is False and not tool.get("requires_confirmation"):
            errors.append(f"{prefix} writes files, is not safe by default, and has no confirmation flag")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/tool_registry.json")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    registry_path = Path(args.registry)
    project_root = Path(args.project_root).resolve()
    registry = load_registry(registry_path)
    errors = validate_tool_registry(registry, project_root)
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
