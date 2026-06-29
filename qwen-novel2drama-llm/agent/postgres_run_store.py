from __future__ import annotations

import json
import os
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

from agent.events import normalize_event, summarize_agent_events
from agent.run_store import RunNotFoundError, RunStore, RunStoreError, lease_is_expired, paginate_run_summaries, run_summary_from_report, run_summary_matches_filters, utc_now, worker_lease_marker
from agent.runtime import now_iso

DEFAULT_POSTGRES_RUN_STORE_DSN_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_DSN"
POSTGRES_RUN_STORE_POOL_ENABLED_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_POOL_ENABLED"
POSTGRES_RUN_STORE_POOL_MIN_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_POOL_MIN"
POSTGRES_RUN_STORE_POOL_MAX_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_POOL_MAX"
POSTGRES_RUN_STORE_POOL_TIMEOUT_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_POOL_TIMEOUT"
POSTGRES_RUN_STORE_REQUIRED_TABLES = ["runs", "run_requests", "run_reports", "run_events", "cancel_requests", "run_artifacts", "run_leases"]

POSTGRES_RUN_STORE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS run_requests (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    request_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS run_reports (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    report_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    event_type TEXT,
    status TEXT,
    created_at TEXT NOT NULL,
    event_json JSONB NOT NULL,
    PRIMARY KEY(run_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_run_events_run_created ON run_events(run_id, created_at, event_id);
CREATE TABLE IF NOT EXISTS cancel_requests (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    marker_json JSONB NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_artifacts (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT,
    artifact_json JSONB NOT NULL,
    PRIMARY KEY(run_id, name)
);
CREATE TABLE IF NOT EXISTS run_leases (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL,
    lease_json JSONB NOT NULL,
    lease_expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_leases_status_expires ON run_leases(status, lease_expires_at);
"""


class PostgresRunStoreUnavailable(RunStoreError):
    pass


@dataclass(frozen=True)
class PostgresConnectionProfile:
    pool_enabled: bool = False
    pool_min_size: int = 1
    pool_max_size: int = 5
    pool_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "PostgresConnectionProfile":
        return cls(
            pool_enabled=bool_from_env(POSTGRES_RUN_STORE_POOL_ENABLED_ENV, False),
            pool_min_size=int_from_env(POSTGRES_RUN_STORE_POOL_MIN_ENV, 1),
            pool_max_size=int_from_env(POSTGRES_RUN_STORE_POOL_MAX_ENV, 5),
            pool_timeout=float_from_env(POSTGRES_RUN_STORE_POOL_TIMEOUT_ENV, 30.0),
        )

    def normalized(self) -> "PostgresConnectionProfile":
        min_size = max(1, int(self.pool_min_size))
        max_size = max(min_size, int(self.pool_max_size))
        timeout = max(1.0, float(self.pool_timeout))
        return PostgresConnectionProfile(pool_enabled=bool(self.pool_enabled), pool_min_size=min_size, pool_max_size=max_size, pool_timeout=timeout)


def bool_from_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def int_from_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def float_from_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


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
    if path is None:
        return POSTGRES_RUN_STORE_SCHEMA_SQL
    return Path(path).read_text(encoding="utf-8")


def apply_schema_sql(conn: Any, sql: str) -> int:
    statements = split_sql_statements(sql)
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()
    return len(statements)


class PostgresRunStore(RunStore):
    """Postgres-backed Agent run store.

    psycopg and psycopg_pool are optional. Core tests can import this module without
    installing the Postgres profile; real operations require the optional profile and a DSN.
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        output_root: Path | str | None = None,
        connect: bool = False,
        auto_init: bool = False,
        connect_factory: Callable[[str], Any] | None = None,
        connection_profile: PostgresConnectionProfile | None = None,
    ) -> None:
        self.dsn = dsn or os.environ.get(DEFAULT_POSTGRES_RUN_STORE_DSN_ENV) or ""
        self.output_root = Path(output_root or "outputs/agent_runtime/postgres")
        self.connect = bool(connect)
        self.auto_init = bool(auto_init)
        self.connect_factory = connect_factory
        self.connection_profile = (connection_profile or PostgresConnectionProfile.from_env()).normalized()
        self._pool: Any | None = None
        if self.connect and self.auto_init:
            self.init_db()

    def _psycopg_connect_factory(self) -> Callable[[str], Any]:
        if self.connect_factory:
            return self.connect_factory
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except Exception as exc:  # noqa: BLE001
            raise PostgresRunStoreUnavailable("psycopg is not installed; install requirements/postgres-run-store.txt before using PostgresRunStore") from exc

        def _connect(dsn: str) -> Any:
            return connect(dsn, row_factory=dict_row)

        return _connect

    def _connect(self) -> Any:
        if not self.dsn:
            raise PostgresRunStoreUnavailable(f"Postgres DSN is not configured; set {DEFAULT_POSTGRES_RUN_STORE_DSN_ENV} or pass postgres_dsn")
        return self._psycopg_connect_factory()(self.dsn)

    def _connection_pool(self) -> Any:
        if not self.dsn:
            raise PostgresRunStoreUnavailable(f"Postgres DSN is not configured; set {DEFAULT_POSTGRES_RUN_STORE_DSN_ENV} or pass postgres_dsn")
        if self._pool is None:
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except Exception as exc:  # noqa: BLE001
                raise PostgresRunStoreUnavailable("psycopg_pool is not installed; install requirements/postgres-run-store.txt before enabling the Postgres connection pool") from exc
            self._pool = ConnectionPool(
                conninfo=self.dsn,
                min_size=self.connection_profile.pool_min_size,
                max_size=self.connection_profile.pool_max_size,
                timeout=self.connection_profile.pool_timeout,
                kwargs={"row_factory": dict_row},
            )
        return self._pool

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self.connection_profile.pool_enabled and self.connect_factory is None:
            with self._connection_pool().connection() as conn:
                yield conn
        else:
            with self._connect() as conn:
                yield conn

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def init_db(self, *, sql: str | None = None, sql_path: Path | str | None = None) -> dict[str, Any]:
        selected_sql = sql if sql is not None else load_schema_sql(sql_path)
        with self._connection() as conn:
            statement_count = apply_schema_sql(conn, selected_sql)
        return {"status": "ok", "statement_count": statement_count, "run_store": self.metadata()}

    def safe_run_id(self, run_id: str) -> str:
        value = str(run_id or "").strip()
        if not value or "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"invalid run_id: {run_id}")
        return value

    def run_dir(self, run_id: str) -> Path:
        return self.output_root / self.safe_run_id(run_id)

    def artifact_path(self, run_id: str, name: str) -> Path:
        return self.run_dir(run_id) / name

    def _json(self, data: Any) -> str:
        return json.dumps(deepcopy(data), ensure_ascii=False, sort_keys=True)

    def _decode_json(self, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return deepcopy(value)

    def _ensure_run(self, cur: Any, run_id: str, *, status: str | None = None, error: str | None = None, completed_at: str | None = None, created_at: str | None = None, updated_at: str | None = None) -> None:
        current = now_iso()
        cur.execute(
            """
            INSERT INTO runs(run_id, status, created_at, updated_at, completed_at, error)
            VALUES(%s, %s, %s, %s, %s, %s)
            ON CONFLICT(run_id) DO UPDATE SET
                status=COALESCE(EXCLUDED.status, runs.status),
                updated_at=EXCLUDED.updated_at,
                completed_at=COALESCE(EXCLUDED.completed_at, runs.completed_at),
                error=COALESCE(EXCLUDED.error, runs.error)
            """,
            (run_id, status, created_at or current, updated_at or current, completed_at, error),
        )

    def _require_run(self, cur: Any, run_id: str) -> dict[str, Any]:
        cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,))
        row = cur.fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return dict(row)

    def load_request(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT request_json FROM run_requests WHERE run_id = %s", (safe_id,))
                row = cur.fetchone()
                if row is None:
                    raise RunNotFoundError(safe_id)
                return self._decode_json(row["request_json"])

    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._ensure_run(cur, safe_id, status=request.get("status") or "created", created_at=request.get("created_at"), updated_at=request.get("updated_at"))
                cur.execute("INSERT INTO run_requests(run_id, request_json) VALUES(%s, %s::jsonb) ON CONFLICT(run_id) DO UPDATE SET request_json=EXCLUDED.request_json", (safe_id, self._json(request)))
            conn.commit()
        return self.artifact_path(safe_id, "agent_request.json")

    def load_report(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT report_json FROM run_reports WHERE run_id = %s", (safe_id,))
                row = cur.fetchone()
                if row is None:
                    raise RunNotFoundError(safe_id)
                return self._decode_json(row["report_json"])

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._ensure_run(cur, safe_id, status=report.get("status"), error=report.get("error"), completed_at=report.get("completed_at"), created_at=report.get("created_at"), updated_at=report.get("updated_at"))
                cur.execute("INSERT INTO run_reports(run_id, report_json) VALUES(%s, %s::jsonb) ON CONFLICT(run_id) DO UPDATE SET report_json=EXCLUDED.report_json", (safe_id, self._json(report)))
            conn.commit()
        return self.artifact_path(safe_id, "agent_run_report.json")

    def append_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        normalized = normalize_event({**event, "run_id": event.get("run_id") or safe_id})
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._ensure_run(cur, safe_id, status=normalized.get("status"))
                cur.execute(
                    """
                    INSERT INTO run_events(run_id, event_id, event_type, status, created_at, event_json)
                    VALUES(%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT(run_id, event_id) DO UPDATE SET
                        event_type=EXCLUDED.event_type,
                        status=EXCLUDED.status,
                        created_at=EXCLUDED.created_at,
                        event_json=EXCLUDED.event_json
                    """,
                    (safe_id, normalized["event_id"], normalized.get("event_type"), normalized.get("status"), normalized["created_at"], self._json(normalized)),
                )
            conn.commit()
        return normalized

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._require_run(cur, safe_id)
                cur.execute("SELECT event_json FROM run_events WHERE run_id = %s ORDER BY created_at, event_id", (safe_id,))
                return [self._decode_json(row["event_json"]) for row in cur.fetchall()]

    def event_summary(self, run_id: str) -> dict[str, Any]:
        return summarize_agent_events(self.load_events(run_id))

    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT marker_json FROM cancel_requests WHERE run_id = %s", (safe_id,))
                row = cur.fetchone()
                return self._decode_json(row["marker_json"]) if row else None

    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        created_at = marker.get("created_at") or now_iso()
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._ensure_run(cur, safe_id, status="cancel_requested", updated_at=created_at)
                cur.execute("INSERT INTO cancel_requests(run_id, marker_json, created_at) VALUES(%s, %s::jsonb, %s) ON CONFLICT(run_id) DO UPDATE SET marker_json=EXCLUDED.marker_json, created_at=EXCLUDED.created_at", (safe_id, self._json(marker), created_at))
            conn.commit()
        return self.artifact_path(safe_id, "cancel_requested.json")

    def cancel_requested(self, run_id: str) -> bool:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM cancel_requests WHERE run_id = %s", (safe_id,))
                return cur.fetchone() is not None

    def save_artifact(self, run_id: str, name: str, artifact: dict[str, Any], *, path: str | None = None) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._ensure_run(cur, safe_id)
                cur.execute("INSERT INTO run_artifacts(run_id, name, path, artifact_json) VALUES(%s, %s, %s, %s::jsonb) ON CONFLICT(run_id, name) DO UPDATE SET path=EXCLUDED.path, artifact_json=EXCLUDED.artifact_json", (safe_id, name, path, self._json(artifact)))
            conn.commit()
        return self.artifact_path(safe_id, name)

    def list_runs(
        self,
        *,
        status: str | None = None,
        owner_id: str | None = None,
        project_id: str | None = None,
        workspace_id: str | None = None,
        parent_run_id: str | None = None,
        query: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order: str | None = None,
    ) -> dict[str, Any]:
        summaries: list[dict[str, Any]] = []
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM runs")
                rows = cur.fetchall()
                for row in rows:
                    run_id = row["run_id"]
                    cur.execute("SELECT report_json FROM run_reports WHERE run_id = %s", (run_id,))
                    report_row = cur.fetchone()
                    cur.execute("SELECT request_json FROM run_requests WHERE run_id = %s", (run_id,))
                    request_row = cur.fetchone()
                    report = self._decode_json(report_row["report_json"]) if report_row else {}
                    request = self._decode_json(request_row["request_json"]) if request_row else {}
                    fallback = {**request, **report}
                    fallback.setdefault("status", row.get("status"))
                    fallback.setdefault("error", row.get("error"))
                    fallback.setdefault("created_at", row.get("created_at"))
                    fallback.setdefault("updated_at", row.get("updated_at"))
                    fallback.setdefault("completed_at", row.get("completed_at"))
                    cur.execute("SELECT COUNT(*) AS count FROM run_artifacts WHERE run_id = %s", (run_id,))
                    count_row = cur.fetchone() or {"count": 0}
                    artifact_count = int(count_row.get("count") or 0)
                    fallback.setdefault("artifacts", {"_indexed_count": artifact_count} if artifact_count else {})
                    summary = run_summary_from_report(run_id, fallback, run_store=self.metadata())
                    if run_summary_matches_filters(summary, status=status, owner_id=owner_id, project_id=project_id, workspace_id=workspace_id, parent_run_id=parent_run_id, query=query):
                        summaries.append(summary)
        page = paginate_run_summaries(summaries, limit=limit, offset=offset, order=order)
        return {**page, "run_store": self.metadata(), "filters": {"status": status, "owner_id": owner_id, "project_id": project_id, "workspace_id": workspace_id, "parent_run_id": parent_run_id, "query": query}}

    def load_worker_lease(self, run_id: str) -> dict[str, Any] | None:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT lease_json FROM run_leases WHERE run_id = %s", (safe_id,))
                row = cur.fetchone()
                return self._decode_json(row["lease_json"]) if row else None

    def _save_lease(self, cur: Any, run_id: str, lease: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO run_leases(run_id, worker_id, lease_json, lease_expires_at, status, updated_at)
            VALUES(%s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT(run_id) DO UPDATE SET
                worker_id=EXCLUDED.worker_id,
                lease_json=EXCLUDED.lease_json,
                lease_expires_at=EXCLUDED.lease_expires_at,
                status=EXCLUDED.status,
                updated_at=EXCLUDED.updated_at
            """,
            (run_id, lease.get("worker_id"), self._json(lease), lease.get("lease_expires_at"), lease.get("status") or "claimed", lease.get("renewed_at") or now_iso()),
        )

    def claim_run(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._require_run(cur, safe_id)
                cur.execute("SELECT lease_json FROM run_leases WHERE run_id = %s FOR UPDATE", (safe_id,))
                row = cur.fetchone()
                existing = self._decode_json(row["lease_json"]) if row else None
                if existing and existing.get("status") == "claimed" and not lease_is_expired(existing, at=current) and existing.get("worker_id") != worker_id:
                    conn.commit()
                    return {"claimed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "already_claimed", "run_store": self.metadata()}
                lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
                if existing and existing.get("worker_id") == worker_id:
                    lease["claimed_at"] = existing.get("claimed_at") or lease["claimed_at"]
                self._save_lease(cur, safe_id, lease)
            conn.commit()
        return {"claimed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._require_run(cur, safe_id)
                cur.execute("SELECT lease_json FROM run_leases WHERE run_id = %s FOR UPDATE", (safe_id,))
                row = cur.fetchone()
                existing = self._decode_json(row["lease_json"]) if row else None
                if not existing or existing.get("status") != "claimed":
                    conn.commit()
                    return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
                if existing.get("worker_id") != worker_id:
                    conn.commit()
                    return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
                if lease_is_expired(existing, at=current):
                    conn.commit()
                    return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "lease_expired", "run_store": self.metadata()}
                lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
                lease["claimed_at"] = existing.get("claimed_at") or lease["claimed_at"]
                self._save_lease(cur, safe_id, lease)
            conn.commit()
        return {"renewed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def release_run(self, run_id: str, worker_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connection() as conn:
            with conn.cursor() as cur:
                self._require_run(cur, safe_id)
                cur.execute("SELECT lease_json FROM run_leases WHERE run_id = %s FOR UPDATE", (safe_id,))
                row = cur.fetchone()
                existing = self._decode_json(row["lease_json"]) if row else None
                if not existing or existing.get("status") != "claimed":
                    conn.commit()
                    return {"released": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
                if existing.get("worker_id") != worker_id:
                    conn.commit()
                    return {"released": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
                released = {**existing, "status": "released", "released_at": current.isoformat()}
                self._save_lease(cur, safe_id, released)
            conn.commit()
        return {"released": True, "run_id": safe_id, "worker_id": worker_id, "lease": released, "run_store": self.metadata()}

    def find_expired_leases(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT lease_json FROM run_leases WHERE status = 'claimed' ORDER BY lease_expires_at")
                rows = cur.fetchall()
        expired: list[dict[str, Any]] = []
        for row in rows:
            lease = self._decode_json(row["lease_json"])
            if lease_is_expired(lease, at=current):
                expired.append({**lease, "run_store": self.metadata()})
        return expired

    def status(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connection() as conn:
            with conn.cursor() as cur:
                row = self._require_run(cur, safe_id)
                cur.execute("SELECT name, path, artifact_json FROM run_artifacts WHERE run_id = %s ORDER BY name", (safe_id,))
                artifact_rows = cur.fetchall()
        try:
            report = self.load_report(safe_id)
        except RunNotFoundError:
            report = {}
        artifacts = report.get("artifacts") or {r["name"]: r.get("path") or self._decode_json(r["artifact_json"]) for r in artifact_rows}
        return {"run_id": safe_id, "status": report.get("status") or row.get("status"), "error": report.get("error") or row.get("error"), "created_at": report.get("created_at") or row.get("created_at"), "updated_at": report.get("updated_at") or row.get("updated_at"), "completed_at": report.get("completed_at") or row.get("completed_at"), "cancel_requested": self.cancel_requested(safe_id), "worker_lease": self.load_worker_lease(safe_id), "artifacts": artifacts, "event_summary": self.event_summary(safe_id), "run_store": self.metadata()}

    def metadata(self) -> dict[str, Any]:
        return {
            "type": "postgres",
            "dsn_configured": bool(self.dsn),
            "dsn_env": DEFAULT_POSTGRES_RUN_STORE_DSN_ENV,
            "output_root": str(self.output_root),
            "connect_on_init": self.connect,
            "auto_init": self.auto_init,
            "implementation_status": "persistence_v1",
            "connection_profile": asdict(self.connection_profile),
        }


def postgres_run_store(
    dsn: str | None = None,
    *,
    output_root: Path | str | None = None,
    connect: bool = False,
    auto_init: bool = False,
    connect_factory: Callable[[str], Any] | None = None,
    connection_profile: PostgresConnectionProfile | None = None,
) -> PostgresRunStore:
    return PostgresRunStore(dsn, output_root=output_root, connect=connect, auto_init=auto_init, connect_factory=connect_factory, connection_profile=connection_profile)
