from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_tools(registry: dict[str, Any], category: str | None = None, safe_only: bool = False) -> list[dict[str, Any]]:
    tools = registry.get("tools", [])
    if category:
        tools = [tool for tool in tools if tool.get("category") == category]
    if safe_only:
        tools = [tool for tool in tools if tool.get("safe_by_default") is True]
    return tools


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/tool_registry.json")
    parser.add_argument("--category", default=None)
    parser.add_argument("--safe-only", action="store_true")
    args = parser.parse_args()
    registry = load_registry(Path(args.registry))
    tools = filter_tools(registry, args.category, args.safe_only)
    print(
        json.dumps(
            {
                "registry_name": registry.get("registry_name"),
                "purpose": registry.get("purpose"),
                "tools": tools,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
