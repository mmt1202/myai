from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inference.model_router import route_model
from services.model_preferences import resolve_model_preferences
from services.model_settings import delete_runtime_model_setting, get_model_setting, load_runtime_policy, model_routing_policy_path_from_env, update_runtime_model_setting


def model_instances_registry(project_root: Path) -> dict[str, Any]:
    return json.loads((project_root / "configs" / "model_instance_registry.json").read_text(encoding="utf-8"))


def list_model_settings(project_root: Path) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    return {
        "policy_name": policy.get("policy_name"),
        "policy_path": str(model_routing_policy_path_from_env(project_root)),
        "global": policy.get("global") or {},
        "task_routes": policy.get("task_routes") or {},
        "workspaces": policy.get("workspaces") or {},
        "projects": policy.get("projects") or {},
        "guards": policy.get("guards") or {},
    }


def get_workspace_model_settings(project_root: Path, workspace_id: str) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    return {"workspace_id": workspace_id, "setting": get_model_setting(policy, "workspaces", workspace_id), "policy_path": str(model_routing_policy_path_from_env(project_root))}


def set_workspace_model_settings(project_root: Path, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return update_runtime_model_setting(project_root, "workspaces", workspace_id, body)


def delete_workspace_model_settings(project_root: Path, workspace_id: str) -> dict[str, Any]:
    return delete_runtime_model_setting(project_root, "workspaces", workspace_id)


def get_project_model_settings(project_root: Path, project_id: str) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    return {"project_id": project_id, "setting": get_model_setting(policy, "projects", project_id), "policy_path": str(model_routing_policy_path_from_env(project_root))}


def set_project_model_settings(project_root: Path, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return update_runtime_model_setting(project_root, "projects", project_id, body)


def delete_project_model_settings(project_root: Path, project_id: str) -> dict[str, Any]:
    return delete_runtime_model_setting(project_root, "projects", project_id)


def resolve_model_preferences_api(project_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    return {"preferences": resolve_model_preferences(body, policy), "policy_path": str(model_routing_policy_path_from_env(project_root))}


def route_with_model_settings_api(project_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    policy = load_runtime_policy(project_root)
    route = route_model(body, model_instances_registry(project_root), policy=policy)
    return {"route": route, "policy_path": str(model_routing_policy_path_from_env(project_root))}
