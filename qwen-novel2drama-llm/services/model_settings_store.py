from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MODEL_SETTINGS_PATH = Path("outputs/model_settings/model_settings.json")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_settings_path_from_env(project_root: Path | None = None) -> Path:
    configured = os.environ.get("FOUNDATION_MODEL_SETTINGS_STORE") or os.environ.get("MYAI_MODEL_SETTINGS_STORE")
    if configured:
        return Path(configured)
    root = project_root or Path.cwd()
    return root / DEFAULT_MODEL_SETTINGS_PATH


def ensure_safe_id(value: str, *, field_name: str = "id") -> str:
    text = str(value or "").strip()
    if not SAFE_ID.match(text):
        raise ValueError(f"invalid {field_name}: {value}")
    return text


def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    primary = settings.get("primary") or settings.get("primary_model")
    fallback = settings.get("fallback") or settings.get("fallback_models") or []
    task_routes = settings.get("task_routes") or {}
    result: dict[str, Any] = {}
    if primary:
        result["primary"] = str(primary)
    result["fallback"] = [str(item) for item in fallback]
    if task_routes:
        result["task_routes"] = task_routes
    result["metadata"] = settings.get("metadata") or {}
    result["updated_at"] = settings.get("updated_at") or now_iso()
    return result


def empty_settings_doc() -> dict[str, Any]:
    return {"version": 1, "workspaces": {}, "projects": {}, "updated_at": now_iso()}


class ModelSettingsStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def metadata(self) -> dict[str, Any]:
        return {"type": "json", "path": str(self.path)}

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_settings_doc()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data.setdefault("version", 1)
        data.setdefault("workspaces", {})
        data.setdefault("projects", {})
        return data

    def write(self, data: dict[str, Any]) -> dict[str, Any]:
        data = {**data, "updated_at": now_iso()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return data

    def get_scope(self, scope: str, scope_id: str) -> dict[str, Any] | None:
        scope_key = self._scope_key(scope)
        safe_id = ensure_safe_id(scope_id, field_name=f"{scope}_id")
        return (self.read().get(scope_key) or {}).get(safe_id)

    def set_scope(self, scope: str, scope_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        scope_key = self._scope_key(scope)
        safe_id = ensure_safe_id(scope_id, field_name=f"{scope}_id")
        data = self.read()
        data.setdefault(scope_key, {})[safe_id] = normalize_settings(settings)
        self.write(data)
        return data[scope_key][safe_id]

    def delete_scope(self, scope: str, scope_id: str) -> dict[str, Any] | None:
        scope_key = self._scope_key(scope)
        safe_id = ensure_safe_id(scope_id, field_name=f"{scope}_id")
        data = self.read()
        removed = (data.get(scope_key) or {}).pop(safe_id, None)
        self.write(data)
        return removed

    def _scope_key(self, scope: str) -> str:
        if scope in {"workspace", "workspaces"}:
            return "workspaces"
        if scope in {"project", "projects"}:
            return "projects"
        raise ValueError(f"unsupported settings scope: {scope}")


def overlay_model_settings(policy: dict[str, Any], settings_doc: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(policy)
    merged.setdefault("workspaces", {}).update(settings_doc.get("workspaces") or {})
    merged.setdefault("projects", {}).update(settings_doc.get("projects") or {})
    return merged


def load_policy_with_runtime_settings(policy: dict[str, Any], *, project_root: Path | None = None) -> dict[str, Any]:
    store = ModelSettingsStore(model_settings_path_from_env(project_root))
    return overlay_model_settings(policy, store.read())
