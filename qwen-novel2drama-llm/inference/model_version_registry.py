from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ModelVersionError(ValueError):
    pass


def load_model_versions(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)
    if not registry_path.exists():
        raise FileNotFoundError(f"model version registry not found: {registry_path}")
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    data.setdefault("active_version", None)
    data.setdefault("versions", [])
    return data


def resolve_model_version(path: str | Path, version: str | None = None) -> dict[str, Any]:
    data = load_model_versions(path)
    target_version = version or data.get("active_version")
    if not target_version:
        raise ModelVersionError("active_version is not set")
    for item in data.get("versions", []):
        if item.get("version") == target_version:
            return item
    raise ModelVersionError(f"model version not found: {target_version}")


def resolve_model_paths(path: str | Path, version: str | None = None) -> tuple[str, str | None, dict[str, Any]]:
    item = resolve_model_version(path, version)
    model_path = item.get("merged_model_path") or item.get("base_model")
    adapter_path = item.get("adapter_path")
    if not model_path:
        raise ModelVersionError(f"model version {item.get('version')} has no model path")
    return str(model_path), str(adapter_path) if adapter_path else None, item
