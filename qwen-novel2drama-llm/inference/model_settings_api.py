from __future__ import annotations

from pathlib import Path
from typing import Any

from inference.model_router import route_model
from services.model_preferences import load_model_routing_policy, resolve_model_preferences
from services.model_settings_store import ModelSettingsStore, model_settings_path_from_env
from skills.registry import load_json


def model_settings_store(project_root: Path) -> ModelSettingsStore:
    return ModelSettingsStore(model_settings_path_from_env(project_root))


def list_model_settings(project_root: Path) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"settings": store.read(), "store": store.metadata()}


def get_workspace_model_settings(project_root: Path, workspace_id: str) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"workspace_id": workspace_id, "settings": store.get_scope("workspace", workspace_id), "store": store.metadata()}


def set_workspace_model_settings(project_root: Path, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"workspace_id": workspace_id, "settings": store.set_scope("workspace", workspace_id, body), "store": store.metadata()}


def delete_workspace_model_settings(project_root: Path, workspace_id: str) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"workspace_id": workspace_id, "removed": store.delete_scope("workspace", workspace_id), "store": store.metadata()}


def get_project_model_settings(project_root: Path, project_id: str) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"project_id": project_id, "settings": store.get_scope("project", project_id), "store": store.metadata()}


def set_project_model_settings(project_root: Path, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"project_id": project_id, "settings": store.set_scope("project", project_id, body), "store": store.metadata()}


def delete_project_model_settings(project_root: Path, project_id: str) -> dict[str, Any]:
    store = model_settings_store(project_root)
    return {"project_id": project_id, "removed": store.delete_scope("project", project_id), "store": store.metadata()}


def resolve_model_preferences_api(project_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    policy = load_model_routing_policy(project_root / "configs" / "model_routing_policy.json")
    return {"preferences": resolve_model_preferences(body, policy), "policy_name": policy.get("policy_name")}


def route_with_model_settings_api(project_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    policy = load_model_routing_policy(project_root / "configs" / "model_routing_policy.json")
    registry = load_json(project_root / "configs" / "model_instance_registry.json")
    return {"route": route_model(body, registry, policy=policy), "policy_name": policy.get("policy_name")}
