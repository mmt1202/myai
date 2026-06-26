from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_capabilities(registry: dict[str, Any], domain: str | None = None, priority: str | None = None, drama_relevance: str | None = None) -> list[dict[str, Any]]:
    items = registry.get("capabilities", [])
    if domain:
        items = [item for item in items if item.get("domain") == domain]
    if priority:
        items = [item for item in items if item.get("priority") == priority]
    if drama_relevance:
        items = [item for item in items if item.get("drama_relevance") == drama_relevance]
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/model_capability_registry.json")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--priority", default=None)
    parser.add_argument("--drama-relevance", default=None)
    args = parser.parse_args()
    registry = load_registry(Path(args.registry))
    print(json.dumps({"registry_name": registry.get("registry_name"), "capabilities": filter_capabilities(registry, args.domain, args.priority, args.drama_relevance)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
