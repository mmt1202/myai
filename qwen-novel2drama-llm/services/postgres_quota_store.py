from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from services.quota_store import QuotaStore, now_iso, numeric_usage, safe_period_key

DEFAULT_POSTGRES_QUOTA_DSN_ENV = "FOUNDATION_QUOTA_POSTGRES_DSN"
POSTGRES_QUOTA_REQUIRED_TABLES = ["rate_limit_buckets", "workspace_usage", "workspace_quota_events"]

POSTGRES_QUOTA_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    window_start INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_usage (
    workspace_id TEXT NOT NULL,
    period_key TEXT NOT NULL,
    usage_json JSONB NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, period_key)
);
CREATE INDEX IF NOT EXISTS idx_workspace_usage_workspace_period ON workspace_usage(workspace_id, period_key);
CREATE TABLE IF NOT EXISTS workspace_quota_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    event_json JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workspace_quota_events_workspace_created ON workspace_quota_events(workspace_id, created_at, id);
"""


class PostgresQuotaStoreUnavailable(RuntimeError):
    pass


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    previous = ""
    for char in sql:
        if char == "'" and previous != "\\" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and previous != "\\" and not in_single_quote:
            in_double_quote = not in_double_quote
        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        previous = char
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def load_schema_sql(path: Path | str | None = None) -> str:
    return POSTGRES_QUOTA_SCHEMA_SQL if path is None else Path(path).read_text(encoding="utf-8")


def apply_schema_sql(conn: Any, sql: str) -> int:
    statements = split_sql_statements(sql)
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()
    return len(statements)


class PostgresQuotaStore(QuotaStore):
    """Postgres-backed quota store for shared rate-limit and workspace quota state."""

    def __init__(self, dsn: str | None = None, *, connect: bool = False, auto_init: bool = False, connect_factory: Callable[[str], Any] | None = None) -> None:
        self.dsn = dsn or os.environ.get(DEFAULT_POSTGRES_QUOTA_DSN_ENV) or ""
        self.connect = bool(connect)
        self.auto_init = bool(auto_init)
        self.connect_factory = connect_factory
        if self.connect and self.auto_init:
            self.init_db()

    def metadata(self) -> dict[str, Any]:
        return {"type": "postgres", "implementation_status": "persistence_v1", "dsn_configured": bool(self.dsn), "dsn_env": DEFAULT_POSTGRES_QUOTA_DSN_ENV}

    def _psycopg_connect_factory(self) -> Callable[[str], Any]:
        if self.connect_factory:
            return self.connect_factory
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except Exception as exc:  # noqa: BLE001
            raise PostgresQuotaStoreUnavailable("psycopg is not installed; install requirements/postgres-quota.txt before using PostgresQuotaStore") from exc

        def _connect(dsn: str) -> Any:
            return connect(dsn, row_factory=dict_row)

        return _connect

    def _connect(self) -> Any:
        if not self.dsn:
            raise PostgresQuotaStoreUnavailable(f"Postgres quota DSN is not configured; set {DEFAULT_POSTGRES_QUOTA_DSN_ENV} or pass postgres_dsn")
        return self._psycopg_connect_factory()(self.dsn)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._connect() as conn:
            yield conn

    def init_db(self, *, sql: str | None = None, sql_path: Path | str | None = None) -> dict[str, Any]:
        selected_sql = sql if sql is not None else load_schema_sql(sql_path)
        with self._connection() as conn:
            statement_count = apply_schema_sql(conn, selected_sql)
        return {"status": "ok", "statement_count": statement_count, "quota_store": self.metadata()}

    def _decode_json(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else (value or {})

    def check_rate_limit_bucket(self, *, bucket: str, limit: int, window_seconds: int, now: int) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("SELECT count, window_start FROM rate_limit_buckets WHERE bucket = %s FOR UPDATE", (bucket,))
                row = cur.fetchone()
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
                allowed = count < limit
                if allowed:
                    count += 1
                cur.execute("""
                    INSERT INTO rate_limit_buckets(bucket, count, window_start, updated_at)
                    VALUES(%s, %s, %s, %s)
                    ON CONFLICT(bucket) DO UPDATE SET count=EXCLUDED.count, window_start=EXCLUDED.window_start, updated_at=EXCLUDED.updated_at
                    """, (bucket, count, window_start, now_iso()))
            conn.commit()
        return {"allowed": allowed, "limit": limit, "remaining": max(0, limit - count), "reset_at": reset_at, "retry_after_seconds": 0 if allowed else max(1, reset_at - now), "bucket": bucket, "count": count, "run_store": self.metadata()}

    def workspace_current_usage(self, *, workspace_id: str, period_key: str, usage_keys: list[str]) -> dict[str, float]:
        period = safe_period_key(period_key)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT usage_json FROM workspace_usage WHERE workspace_id = %s AND period_key = %s", (workspace_id, period))
                row = cur.fetchone()
        return numeric_usage(self._decode_json(row["usage_json"]) if row else {}, usage_keys)

    def record_workspace_usage(self, *, workspace_id: str, period_increments: dict[str, dict[str, float]], event: dict[str, Any], usage_keys: list[str]) -> dict[str, Any]:
        updated_periods: dict[str, dict[str, float]] = {}
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                for key, increment in period_increments.items():
                    period = safe_period_key(key)
                    cur.execute("SELECT usage_json FROM workspace_usage WHERE workspace_id = %s AND period_key = %s FOR UPDATE", (workspace_id, period))
                    row = cur.fetchone()
                    current = numeric_usage(self._decode_json(row["usage_json"]) if row else {}, usage_keys)
                    updated = {metric: current.get(metric, 0.0) + float(increment.get(metric, 0.0) or 0.0) for metric in usage_keys}
                    cur.execute("""
                        INSERT INTO workspace_usage(workspace_id, period_key, usage_json, updated_at)
                        VALUES(%s, %s, %s::jsonb, %s)
                        ON CONFLICT(workspace_id, period_key) DO UPDATE SET usage_json=EXCLUDED.usage_json, updated_at=EXCLUDED.updated_at
                        """, (workspace_id, period, json.dumps(updated, ensure_ascii=False, sort_keys=True), now_iso()))
                    updated_periods[period] = updated
                cur.execute("INSERT INTO workspace_quota_events(created_at, workspace_id, event_json) VALUES(%s, %s, %s::jsonb)", (event.get("created_at") or now_iso(), workspace_id, json.dumps(event, ensure_ascii=False, sort_keys=True)))
            conn.commit()
        return {"workspace_id": workspace_id, "updated_periods": updated_periods, "event": event, "run_store": self.metadata()}
