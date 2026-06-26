from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any


class RateLimitError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int, limit: int, remaining: int, reset_at: int) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
        }


def rate_limit_enabled_from_env() -> bool:
    value = os.environ.get("FOUNDATION_RATE_LIMIT_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def rate_limit_config_path_from_env(project_root: Path) -> Path:
    configured = os.environ.get("FOUNDATION_RATE_LIMITS")
    if configured:
        return Path(configured)
    return project_root / "configs" / "auth" / "rate_limits.json"


def rate_limit_state_path_from_env(project_root: Path) -> Path:
    configured = os.environ.get("FOUNDATION_RATE_LIMIT_STATE")
    if configured:
        return Path(configured)
    return project_root / "outputs" / "auth" / "rate_limit_state.json"


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_limit(config: dict[str, Any], *, key_id: str, required_scope: str | None) -> dict[str, Any]:
    default = config.get("default") or {"enabled": False, "limit": 0, "window_seconds": 60}
    by_scope = (config.get("by_scope") or {}).get(required_scope or "") or {}
    by_key = (config.get("by_key_id") or {}).get(key_id or "") or {}
    merged = {**default, **by_scope, **by_key}
    return {
        "enabled": bool(merged.get("enabled", True)),
        "limit": int(merged.get("limit") or 0),
        "window_seconds": int(merged.get("window_seconds") or 60),
    }


def bucket_key(key_id: str, required_scope: str | None, workspace_id: str | None) -> str:
    return "|".join([key_id or "anonymous", required_scope or "public", workspace_id or "default"])


def check_rate_limit(
    state_path: Path,
    config: dict[str, Any],
    *,
    key_id: str,
    required_scope: str | None,
    workspace_id: str | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    policy = resolve_limit(config, key_id=key_id, required_scope=required_scope)
    current_time = int(now if now is not None else time.time())
    if not policy["enabled"] or policy["limit"] <= 0:
        return {"allowed": True, "limit": 0, "remaining": -1, "reset_at": current_time, "retry_after_seconds": 0, "bucket": None}
    state = load_json(state_path, {"buckets": {}})
    buckets = state.setdefault("buckets", {})
    key = bucket_key(key_id, required_scope, workspace_id)
    bucket = buckets.get(key) or {"count": 0, "window_start": current_time}
    window_start = int(bucket.get("window_start") or current_time)
    if current_time - window_start >= policy["window_seconds"]:
        bucket = {"count": 0, "window_start": current_time}
        window_start = current_time
    count = int(bucket.get("count") or 0)
    reset_at = window_start + policy["window_seconds"]
    if count >= policy["limit"]:
        save_json(state_path, state)
        raise RateLimitError(
            "rate limit exceeded",
            retry_after_seconds=max(1, reset_at - current_time),
            limit=policy["limit"],
            remaining=0,
            reset_at=reset_at,
        )
    count += 1
    bucket["count"] = count
    bucket["window_start"] = window_start
    buckets[key] = bucket
    save_json(state_path, state)
    return {
        "allowed": True,
        "limit": policy["limit"],
        "remaining": max(0, policy["limit"] - count),
        "reset_at": reset_at,
        "retry_after_seconds": 0,
        "bucket": key,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/auth/rate_limits.json")
    parser.add_argument("--state", default="outputs/auth/rate_limit_state.json")
    parser.add_argument("--key-id", default="anonymous")
    parser.add_argument("--scope", default="foundation:read")
    parser.add_argument("--workspace-id", default=None)
    args = parser.parse_args()
    try:
        result = check_rate_limit(
            Path(args.state),
            load_json(Path(args.config), {"default": {"enabled": True, "limit": 120, "window_seconds": 60}}),
            key_id=args.key_id,
            required_scope=args.scope,
            workspace_id=args.workspace_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except RateLimitError as exc:
        print(json.dumps({"allowed": False, "error": exc.to_dict()}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
