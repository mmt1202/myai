from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USAGE_KEYS = ["requests", "input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cost"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def quota_enabled_from_env() -> bool:
    return bool_from_env("FOUNDATION_WORKSPACE_QUOTA_ENABLED", False)


def quota_config_path_from_env(project_root: Path) -> Path:
    return Path(os.getenv("FOUNDATION_WORKSPACE_QUOTAS", str(project_root / "configs" / "auth" / "workspace_quotas.json")))


def quota_state_path_from_env(project_root: Path) -> Path:
    return Path(os.getenv("FOUNDATION_WORKSPACE_QUOTA_STATE", str(project_root / "outputs" / "auth" / "workspace_quota_state.json")))


def number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_workspace_limits(config: dict[str, Any], workspace_id: str | None) -> dict[str, Any]:
    default_limits = config.get("default") or {}
    workspace_limits = ((config.get("workspaces") or {}).get(workspace_id or "") or {})
    return deep_merge(default_limits, workspace_limits)


def period_key(period: str, at: datetime | None = None) -> str:
    current = at or now_utc()
    if period == "daily":
        return current.strftime("daily:%Y-%m-%d")
    if period == "monthly":
        return current.strftime("monthly:%Y-%m")
    raise ValueError(f"unsupported quota period: {period}")


def usage_increment(usage: dict[str, Any] | None, cost: dict[str, Any] | None = None, *, requests: int = 1) -> dict[str, float]:
    raw_usage = usage or {}
    raw_cost = cost or {}
    actual_cost = raw_cost.get("actual")
    if actual_cost is None:
        actual_cost = raw_cost.get("estimated")
    return {
        "requests": float(requests),
        "input_tokens": number(raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens")),
        "output_tokens": number(raw_usage.get("output_tokens") or raw_usage.get("completion_tokens")),
        "reasoning_tokens": number(raw_usage.get("reasoning_tokens")),
        "total_tokens": number(raw_usage.get("total_tokens")) or number(raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens")) + number(raw_usage.get("output_tokens") or raw_usage.get("completion_tokens")) + number(raw_usage.get("reasoning_tokens")),
        "cost": number(actual_cost),
    }


def empty_usage() -> dict[str, float]:
    return {key: 0.0 for key in USAGE_KEYS}


def workspace_state(state: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    state.setdefault("workspaces", {})
    state["workspaces"].setdefault(workspace_id, {})
    return state["workspaces"][workspace_id]


def current_usage_for_period(state: dict[str, Any], workspace_id: str, period: str, at: datetime | None = None) -> dict[str, float]:
    ws_state = workspace_state(state, workspace_id)
    key = period_key(period, at)
    usage = ws_state.get(key) or {}
    merged = empty_usage()
    for item in USAGE_KEYS:
        merged[item] = number(usage.get(item))
    return merged


def projected_usage(current: dict[str, Any], increment: dict[str, Any]) -> dict[str, float]:
    return {key: number(current.get(key)) + number(increment.get(key)) for key in USAGE_KEYS}


def limit_key(metric: str) -> str:
    if metric == "cost":
        return "max_cost"
    return f"max_{metric}"


def check_period_limits(period: str, limits: dict[str, Any], current: dict[str, Any], increment: dict[str, Any]) -> dict[str, Any]:
    period_limits = limits.get(period) or {}
    projected = projected_usage(current, increment)
    violations: list[dict[str, Any]] = []
    for metric in USAGE_KEYS:
        configured_limit = period_limits.get(limit_key(metric))
        if configured_limit is None:
            continue
        max_value = number(configured_limit)
        if max_value <= 0:
            continue
        projected_value = number(projected.get(metric))
        if projected_value > max_value:
            violations.append(
                {
                    "period": period,
                    "metric": metric,
                    "limit": max_value,
                    "current": number(current.get(metric)),
                    "increment": number(increment.get(metric)),
                    "projected": projected_value,
                    "excess": projected_value - max_value,
                }
            )
    return {"period": period, "current": current, "increment": increment, "projected": projected, "violations": violations}


def check_workspace_quota(
    *,
    config: dict[str, Any],
    state: dict[str, Any],
    workspace_id: str | None,
    usage: dict[str, Any] | None,
    cost: dict[str, Any] | None = None,
    at: datetime | None = None,
    requests: int = 1,
) -> dict[str, Any]:
    resolved_workspace = workspace_id or "default"
    limits = resolve_workspace_limits(config, resolved_workspace)
    enabled = bool(limits.get("enabled", config.get("enabled", True)))
    increment = usage_increment(usage, cost, requests=requests)
    period_reports: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    if enabled:
        for period in ["daily", "monthly"]:
            current = current_usage_for_period(state, resolved_workspace, period, at)
            report = check_period_limits(period, limits, current, increment)
            period_reports.append(report)
            violations.extend(report["violations"])
    return {
        "workspace_id": resolved_workspace,
        "enabled": enabled,
        "allowed": enabled is False or not violations,
        "decision": "allowed" if (enabled is False or not violations) else "denied",
        "increment": increment,
        "periods": period_reports,
        "violations": violations,
        "limits": limits,
    }


def add_usage(existing: dict[str, Any], increment: dict[str, Any]) -> dict[str, float]:
    updated = empty_usage()
    for key in USAGE_KEYS:
        updated[key] = number(existing.get(key)) + number(increment.get(key))
    return updated


def record_workspace_usage(
    *,
    state: dict[str, Any],
    workspace_id: str | None,
    usage: dict[str, Any] | None,
    cost: dict[str, Any] | None = None,
    at: datetime | None = None,
    requests: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_workspace = workspace_id or "default"
    current_time = at or now_utc()
    increment = usage_increment(usage, cost, requests=requests)
    ws_state = workspace_state(state, resolved_workspace)
    updated_periods: dict[str, dict[str, float]] = {}
    for period in ["daily", "monthly"]:
        key = period_key(period, current_time)
        ws_state[key] = add_usage(ws_state.get(key) or {}, increment)
        updated_periods[key] = ws_state[key]
    event = {
        "created_at": current_time.isoformat(),
        "workspace_id": resolved_workspace,
        "increment": increment,
        "metadata": metadata or {},
    }
    state.setdefault("events", []).append(event)
    state["events"] = state["events"][-1000:]
    return {"workspace_id": resolved_workspace, "increment": increment, "updated_periods": updated_periods, "event": event}


def check_workspace_quota_from_paths(
    *,
    config_path: Path,
    state_path: Path,
    workspace_id: str | None,
    usage: dict[str, Any] | None,
    cost: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> dict[str, Any]:
    config = load_json(config_path, {"default": {"enabled": False}})
    state = load_json(state_path, {"workspaces": {}, "events": []})
    return check_workspace_quota(config=config, state=state, workspace_id=workspace_id, usage=usage, cost=cost, at=at)


def record_workspace_usage_to_path(
    *,
    state_path: Path,
    workspace_id: str | None,
    usage: dict[str, Any] | None,
    cost: dict[str, Any] | None = None,
    at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_json(state_path, {"workspaces": {}, "events": []})
    result = record_workspace_usage(state=state, workspace_id=workspace_id, usage=usage, cost=cost, at=at, metadata=metadata)
    save_json(state_path, state)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or record workspace quota usage.")
    parser.add_argument("--config", default="configs/auth/workspace_quotas.json")
    parser.add_argument("--state", default="outputs/auth/workspace_quota_state.json")
    parser.add_argument("--workspace-id", default="default")
    parser.add_argument("--usage", required=True, help="JSON usage object")
    parser.add_argument("--cost", default="{}", help="JSON cost object")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()

    usage = json.loads(args.usage)
    cost = json.loads(args.cost)
    if args.record:
        result = record_workspace_usage_to_path(state_path=Path(args.state), workspace_id=args.workspace_id, usage=usage, cost=cost)
    else:
        result = check_workspace_quota_from_paths(config_path=Path(args.config), state_path=Path(args.state), workspace_id=args.workspace_id, usage=usage, cost=cost)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("allowed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
