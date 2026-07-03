from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "configs" / "model_routing_policy.json"
DEFAULT_RUNTIME_PATH = PROJECT_ROOT / "outputs" / "model_settings" / "model_routing_policy.json"


class ModelSettingsError(ValueError):
    pass


def model_routing_policy_path_from_env(project_root: Path | None = None) -> Path:
    configured = os.environ.get("FOUNDATION_MODEL_ROUTING_POLICY_PATH") or os.environ.get("MYAI_MODEL_ROUTING_POLICY_PATH")
    if configured:
        return Path(configured)
    root = project_root or PROJECT_ROOT
    return root / "outputs" / "model_settings" / "model_routing_policy.json"


def load_policy_template(template_path: Path | None = None) -> dict[str, Any]:
    path = template_path or DEFAULT_TEMPLATE_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_runtime_policy(project_root: Path | None = None, *, template_path: Path | None = None, policy_path: Path | None = None) -> Path:
    target = policy_path or model_routing_policy_path_from_env(project_root)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    template = load_policy_template(template_path)
    target.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_runtime_policy(project_root: Path | None = None, *, template_path: Path | None = None, policy_path: Path | None = None) -> dict[str, Any]:
    path = ensure_runtime_policy(project_root, template_path=template_path, policy_path=policy_path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_runtime_policy(policy: dict[str, Any], project_root: Path | None = None, *, policy_path: Path | None = None) -> dict[str, Any]:
    path = policy_path or model_routing_policy_path_from_env(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "path": str(path), "policy_name": policy.get("policy_name")}


def validate_setting_id(value: str, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ModelSettingsError(f"{field} is required")
    if ".." in text or "/" in text or "\\" in text:
        raise ModelSettingsError(f"{field} is invalid")
    return text


def normalize_model_ids(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ModelSettingsError("fallback must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        model_id = str(value or "").strip()
        if not model_id:
            continue
        if model_id not in seen:
            seen.add(model_id)
            result.append(model_id)
    return result


def normalize_model_setting(body: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ModelSettingsError("setting body must be an object")
    primary = body.get("primary") if body.get("primary") is not None else body.get("primary_model")
    fallback = body.get("fallback") if body.get("fallback") is not None else body.get("fallback_models")
    setting: dict[str, Any] = {}
    if primary is not None:
        setting["primary"] = str(primary).strip()
        if not setting["primary"]:
            raise ModelSettingsError("primary model cannot be empty")
    setting["fallback"] = normalize_model_ids(fallback)
    if body.get("metadata") is not None:
        if not isinstance(body.get("metadata"), dict):
            raise ModelSettingsError("metadata must be an object")
        setting["metadata"] = body.get("metadata") or {}
    return setting


def section_for(scope: str) -> str:
    if scope not in {"workspaces", "projects"}:
        raise ModelSettingsError(f"unsupported model setting scope: {scope}")
    return scope


def get_model_setting(policy: dict[str, Any], scope: str, setting_id: str) -> dict[str, Any]:
    section = section_for(scope)
    safe_id = validate_setting_id(setting_id, field=f"{scope}_id")
    return ((policy.get(section) or {}).get(safe_id) or {})


def set_model_setting(policy: dict[str, Any], scope: str, setting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    section = section_for(scope)
    safe_id = validate_setting_id(setting_id, field=f"{scope}_id")
    normalized = normalize_model_setting(body)
    policy.setdefault(section, {})[safe_id] = normalized
    return normalized


def delete_model_setting(policy: dict[str, Any], scope: str, setting_id: str) -> dict[str, Any]:
    section = section_for(scope)
    safe_id = validate_setting_id(setting_id, field=f"{scope}_id")
    existed = safe_id in (policy.get(section) or {})
    if existed:
        policy[section].pop(safe_id, None)
    return {"deleted": existed, "id": safe_id, "scope": section}


def update_runtime_model_setting(project_root: Path, scope: str, setting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    setting = set_model_setting(policy, scope, setting_id, body)
    saved = save_runtime_policy(policy, project_root)
    return {"status": "ok", "scope": scope, "id": setting_id, "setting": setting, "policy_path": saved["path"]}


def delete_runtime_model_setting(project_root: Path, scope: str, setting_id: str) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    result = delete_model_setting(policy, scope, setting_id)
    saved = save_runtime_policy(policy, project_root)
    return {"status": "ok", **result, "policy_path": saved["path"]}
