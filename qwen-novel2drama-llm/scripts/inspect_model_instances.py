from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_instances(registry: dict[str, Any], provider: str | None = None, capability: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    items = registry.get("instances", [])
    if provider:
        items = [item for item in items if item.get("provider") == provider]
    if capability:
        items = [item for item in items if capability in item.get("capabilities", [])]
    if status:
        items = [item for item in items if item.get("status") == status]
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/model_instance_registry.json")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--capability", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args()
    registry = load_registry(Path(args.registry))
    print(json.dumps({"registry_name": registry.get("registry_name"), "instances": filter_instances(registry, args.provider, args.capability, args.status)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
