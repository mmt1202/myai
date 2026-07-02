from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "configs" / "model_routing_policy.json"


def load_model_routing_policy(path: Path | str | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    if not policy_path.exists():
        return {"global": {}, "task_routes": {}, "workspaces": {}, "projects": {}, "guards": {}}
    return json.loads(policy_path.read_text(encoding="utf-8"))


def infer_task_type(request: dict[str, Any]) -> str | None:
    if request.get("task_type"):
        return str(request["task_type"])
    route_mode = str(request.get("route_mode") or "")
    if route_mode == "code_specialist":
        return "coding"
    if route_mode == "drama_specialist":
        return "drama"
    required = set(request.get("required_capabilities") or [])
    if {"vision.understand", "audio.understand", "video.understand"} & required:
        return "multimodal"
    if request.get("privacy", {}).get("local_only"):
        return "private"
    if route_mode == "cheap":
        return "cheap_summary"
    return None


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def workspace_settings(policy: dict[str, Any], workspace_id: str | None) -> dict[str, Any]:
    if not workspace_id:
        return {}
    return (policy.get("workspaces") or {}).get(workspace_id) or {}


def project_settings(policy: dict[str, Any], project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {}
    return (policy.get("projects") or {}).get(project_id) or {}


def task_settings(policy: dict[str, Any], task_type: str | None) -> dict[str, Any]:
    if not task_type:
        return {}
    return (policy.get("task_routes") or {}).get(task_type) or {}


def env_primary_model() -> str | None:
    return os.environ.get("FOUNDATION_PRIMARY_MODEL") or os.environ.get("MYAI_PRIMARY_MODEL")


def env_fallback_models() -> list[str]:
    raw = os.environ.get("FOUNDATION_FALLBACK_MODELS") or os.environ.get("MYAI_FALLBACK_MODELS") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_model_preferences(request: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    active_policy = policy or load_model_routing_policy()
    guards = active_policy.get("guards") or {}
    global_settings = active_policy.get("global") or {}
    task_type = infer_task_type(request)
    workspace_id = request.get("workspace_id") or (request.get("workspace") or {}).get("id")
    project_id = request.get("project_id") or (request.get("project") or {}).get("id")
    workspace = workspace_settings(active_policy, str(workspace_id) if workspace_id else None)
    project = project_settings(active_policy, str(project_id) if project_id else None)
    task = task_settings(active_policy, task_type)
    policy_hits: list[str] = []

    primary = None
    if guards.get("allow_request_override", True):
        primary = request.get("model_id") or request.get("model") or request.get("primary_model")
        if primary:
            policy_hits.append("request_primary")
    if not primary and env_primary_model():
        primary = env_primary_model()
        policy_hits.append("env_primary")
    if not primary and guards.get("allow_project_override", True) and project.get("primary"):
        primary = project.get("primary")
        policy_hits.append("project_primary")
    if not primary and guards.get("allow_workspace_override", True) and workspace.get("primary"):
        primary = workspace.get("primary")
        policy_hits.append("workspace_primary")
    if not primary and task.get("primary"):
        primary = task.get("primary")
        policy_hits.append("task_primary")
    if not primary:
        primary = global_settings.get("default_primary_model")
        if primary:
            policy_hits.append("global_primary")

    fallbacks = []
    fallbacks.extend(request.get("fallback_models") or [])
    fallbacks.extend(env_fallback_models())
    fallbacks.extend(project.get("fallback") or [])
    fallbacks.extend(workspace.get("fallback") or [])
    fallbacks.extend(task.get("fallback") or [])
    fallbacks.extend(global_settings.get("fallback_models") or [])

    privacy = request.get("privacy") or {}
    if privacy.get("local_only") and guards.get("privacy_local_only_forces_private_models", True):
        private_models = global_settings.get("private_models") or []
        primary = private_models[0] if private_models else primary
        fallbacks = private_models[1:]
        policy_hits.append("privacy_guard_private_models")

    preferred = unique_ordered(([str(primary)] if primary else []) + [str(item) for item in fallbacks])
    return {
        "task_type": task_type,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "primary_model": primary,
        "fallback_models": [item for item in preferred if item != primary],
        "preferred_model_ids": preferred,
        "policy_hits": policy_hits,
        "max_estimated_cost": request.get(guards.get("max_cost_request_field", "max_estimated_cost")),
        "policy_name": active_policy.get("policy_name"),
    }


def preference_rank(model_id: str | None, preferences: dict[str, Any]) -> int | None:
    if not model_id:
        return None
    preferred = preferences.get("preferred_model_ids") or []
    try:
        return preferred.index(model_id)
    except ValueError:
        return None


def preference_boost(model_id: str | None, preferences: dict[str, Any]) -> float:
    rank = preference_rank(model_id, preferences)
    if rank is None:
        return 0.0
    return max(0.0, 2.0 - (rank * 0.25))
