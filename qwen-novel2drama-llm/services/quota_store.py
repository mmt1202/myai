from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quota_backend_from_env() -> str:
    value = os.environ.get("FOUNDATION_QUOTA_BACKEND") or os.environ.get("FOUNDATION_RATE_LIMIT_BACKEND") or os.environ.get("FOUNDATION_WORKSPACE_QUOTA_BACKEND") or "file"
    normalized = value.strip().lower().replace("_", "-")
    aliases = {"json": "file", "file-backed": "file", "sqlite3": "sqlite", "sqlite-backed": "sqlite"}
    return aliases.get(normalized, normalized)


def quota_db_path_from_env(default_path: Path) -> Path:
    configured = os.environ.get("FOUNDATION_QUOTA_DB") or os.environ.get("FOUNDATION_RATE_LIMIT_DB") or os.environ.get("FOUNDATION_WORKSPACE_QUOTA_DB")
    return Path(configured) if configured else default_path


def safe_period_key(value: str) -> str:
    key = str(value or "").strip()
    if not key or "/" in key or "\\" in key or ".." in key:
        raise ValueError(f"invalid period key: {value}")
    return key


def numeric_usage(raw: dict[str, Any] | None, usage_keys: list[str]) -> dict[str, float]:
    data = raw or {}
    result: dict[str, float] = {}
    for key in usage_keys:
        value = data.get(key)
        try:
            result[key] = float(value or 0)
        except (TypeError, ValueError):
            result[key] = 0.0
    return result


class QuotaStore:
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    def check_rate_limit_bucket(self, *, bucket: str, limit: int, window_seconds: int, now: int) -> dict[str, Any]:
        raise NotImplementedError

    def workspace_current_usage(self, *, workspace_id: str, period_key: str, usage_keys: list[str]) -> dict[str, float]:
        raise NotImplementedError

    def record_workspace_usage(self, *, workspace_id: str, period_increments: dict[str, dict[str, float]], event: dict[str, Any], usage_keys: list[str]) -> dict[str, Any]:
        raise NotImplementedError


class FileQuotaStore(QuotaStore):
    def __init__(self, *, rate_limit_state_path: Path, workspace_quota_state_path: Path) -> None:
        self.rate_limit_state_path = Path(rate_limit_state_path)
        self.workspace_quota_state_path = Path(workspace_quota_state_path)

    def metadata(self) -> dict[str, Any]:
        return {"type": "file", "rate_limit_state_path": str(self.rate_limit_state_path), "workspace_quota_state_path": str(self.workspace_quota_state_path)}

    def check_rate_limit_bucket(self, *, bucket: str, limit: int, window_seconds: int, now: int) -> dict[str, Any]:
        state = load_json(self.rate_limit_state_path, {"buckets": {}})
        buckets = state.setdefault("buckets", {})
        current = buckets.get(bucket) or {"count": 0, "window_start": now}
        window_start = int(current.get("window_start") or now)
        if now - window_start >= window_seconds:
            current = {"count": 0, "window_start": now}
            window_start = now
        count = int(current.get("count") or 0)
        reset_at = window_start + window_seconds
        if count >= limit:
            save_json(self.rate_limit_state_path, state)
            return {"allowed": False, "limit": limit, "remaining": 0, "reset_at": reset_at, "retry_after_seconds": max(1, reset_at - now), "bucket": bucket, "count": count, "run_store": self.metadata()}
        count += 1
        current["count"] = count
        current["window_start"] = window_start
        buckets[bucket] = current
        save_json(self.rate_limit_state_path, state)
        return {"allowed": True, "limit": limit, "remaining": max(0, limit - count), "reset_at": reset_at, "retry_after_seconds": 0, "bucket": bucket, "count": count, "run_store": self.metadata()}

    def workspace_state(self) -> dict[str, Any]:
        return load_json(self.workspace_quota_state_path, {"workspaces": {}, "events": []})

    def workspace_current_usage(self, *, workspace_id: str, period_key: str, usage_keys: list[str]) -> dict[str, float]:
        state = self.workspace_state()
        raw = ((state.get("workspaces") or {}).get(workspace_id) or {}).get(safe_period_key(period_key)) or {}
        return numeric_usage(raw, usage_keys)

    def record_workspace_usage(self, *, workspace_id: str, period_increments: dict[str, dict[str, float]], event: dict[str, Any], usage_keys: list[str]) -> dict[str, Any]:
        state = self.workspace_state()
        workspaces = state.setdefault("workspaces", {})
        workspace = workspaces.setdefault(workspace_id, {})
        updated_periods: dict[str, dict[str, float]] = {}
        for key, increment in period_increments.items():
            period = safe_period_key(key)
            current = numeric_usage(workspace.get(period) or {}, usage_keys)
            updated = {metric: current.get(metric, 0.0) + float(increment.get(metric, 0.0) or 0.0) for metric in usage_keys}
            workspace[period] = updated
            updated_periods[period] = updated
        state.setdefault("events", []).append(event)
        state["events"] = state["events"][-1000:]
        save_json(self.workspace_quota_state_path, state)
        return {"workspace_id": workspace_id, "updated_periods": updated_periods, "event": event, "run_store": self.metadata()}


class SQLiteQuotaStore(QuotaStore):
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                    bucket TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    window_start INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspace_usage (
                    workspace_id TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    usage_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_id, period_key)
                );
                CREATE TABLE IF NOT EXISTS workspace_quota_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    event_json TEXT NOT NULL
                );
                """
            )

    def metadata(self) -> dict[str, Any]:
        return {"type": "sqlite", "db_path": str(self.db_path)}

    def check_rate_limit_bucket(self, *, bucket: str, limit: int, window_seconds: int, now: int) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT count, window_start FROM rate_limit_buckets WHERE bucket = ?", (bucket,)).fetchone()
            if row is None:
                count = 0
                window_start = now
            else:
                count = int(row["count"] or 0)
                window_start = int(row["window_start"] or now)
                if now - window_start >= window_seconds:
                    count = 0
                    window_start = now
            reset_at = window_start + window_seconds
            if count >= limit:
                conn.execute("INSERT INTO rate_limit_buckets(bucket, count, window_start, updated_at) VALUES(?, ?, ?, ?) ON CONFLICT(bucket) DO UPDATE SET count=excluded.count, window_start=excluded.window_start, updated_at=excluded.updated_at", (bucket, count, window_start, now_iso()))
                return {"allowed": False, "limit": limit, "remaining": 0, "reset_at": reset_at, "retry_after_seconds": max(1, reset_at - now), "bucket": bucket, "count": count, "run_store": self.metadata()}
            count += 1
            conn.execute("INSERT INTO rate_limit_buckets(bucket, count, window_start, updated_at) VALUES(?, ?, ?, ?) ON CONFLICT(bucket) DO UPDATE SET count=excluded.count, window_start=excluded.window_start, updated_at=excluded.updated_at", (bucket, count, window_start, now_iso()))
            return {"allowed": True, "limit": limit, "remaining": max(0, limit - count), "reset_at": reset_at, "retry_after_seconds": 0, "bucket": bucket, "count": count, "run_store": self.metadata()}

    def workspace_current_usage(self, *, workspace_id: str, period_key: str, usage_keys: list[str]) -> dict[str, float]:
        with self._connect() as conn:
            row = conn.execute("SELECT usage_json FROM workspace_usage WHERE workspace_id = ? AND period_key = ?", (workspace_id, safe_period_key(period_key))).fetchone()
            if row is None:
                return numeric_usage({}, usage_keys)
            return numeric_usage(json.loads(row["usage_json"]), usage_keys)

    def record_workspace_usage(self, *, workspace_id: str, period_increments: dict[str, dict[str, float]], event: dict[str, Any], usage_keys: list[str]) -> dict[str, Any]:
        updated_periods: dict[str, dict[str, float]] = {}
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for key, increment in period_increments.items():
                period = safe_period_key(key)
                row = conn.execute("SELECT usage_json FROM workspace_usage WHERE workspace_id = ? AND period_key = ?", (workspace_id, period)).fetchone()
                current = numeric_usage(json.loads(row["usage_json"]) if row else {}, usage_keys)
                updated = {metric: current.get(metric, 0.0) + float(increment.get(metric, 0.0) or 0.0) for metric in usage_keys}
                conn.execute("INSERT INTO workspace_usage(workspace_id, period_key, usage_json, updated_at) VALUES(?, ?, ?, ?) ON CONFLICT(workspace_id, period_key) DO UPDATE SET usage_json=excluded.usage_json, updated_at=excluded.updated_at", (workspace_id, period, json.dumps(updated, ensure_ascii=False, sort_keys=True), now_iso()))
                updated_periods[period] = updated
            conn.execute("INSERT INTO workspace_quota_events(created_at, workspace_id, event_json) VALUES(?, ?, ?)", (event.get("created_at") or now_iso(), workspace_id, json.dumps(event, ensure_ascii=False, sort_keys=True)))
        return {"workspace_id": workspace_id, "updated_periods": updated_periods, "event": event, "run_store": self.metadata()}


def file_quota_store(*, rate_limit_state_path: Path, workspace_quota_state_path: Path) -> FileQuotaStore:
    return FileQuotaStore(rate_limit_state_path=rate_limit_state_path, workspace_quota_state_path=workspace_quota_state_path)


def sqlite_quota_store(db_path: Path | str) -> SQLiteQuotaStore:
    return SQLiteQuotaStore(db_path)


def build_quota_store(kind: str | None, *, rate_limit_state_path: Path, workspace_quota_state_path: Path, sqlite_path: Path | str | None = None) -> QuotaStore:
    normalized = (kind or "file").strip().lower().replace("_", "-")
    aliases = {"json": "file", "file-backed": "file", "sqlite3": "sqlite", "sqlite-backed": "sqlite"}
    normalized = aliases.get(normalized, normalized)
    if normalized == "file":
        return file_quota_store(rate_limit_state_path=rate_limit_state_path, workspace_quota_state_path=workspace_quota_state_path)
    if normalized == "sqlite":
        default_db = workspace_quota_state_path.with_suffix(".sqlite")
        return sqlite_quota_store(Path(sqlite_path) if sqlite_path else default_db)
    raise ValueError(f"unsupported quota store: {kind}")


def quota_store_from_env(*, rate_limit_state_path: Path, workspace_quota_state_path: Path) -> QuotaStore:
    backend = quota_backend_from_env()
    default_db = workspace_quota_state_path.with_suffix(".sqlite")
    return build_quota_store(backend, rate_limit_state_path=rate_limit_state_path, workspace_quota_state_path=workspace_quota_state_path, sqlite_path=quota_db_path_from_env(default_db))
