from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.events import normalize_event, summarize_agent_events
from agent.run_store import RunNotFoundError, RunStore, lease_is_expired, paginate_run_summaries, run_summary_from_report, run_summary_matches_filters, utc_now, worker_lease_marker
from agent.runtime import now_iso


class SQLiteRunStore(RunStore):
    """SQLite-backed Agent run store using only the Python standard library."""

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
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, status TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS run_requests (run_id TEXT PRIMARY KEY, request_json TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS run_reports (run_id TEXT PRIMARY KEY, report_json TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS run_events (run_id TEXT NOT NULL, event_id TEXT NOT NULL, event_type TEXT, status TEXT, created_at TEXT NOT NULL, event_json TEXT NOT NULL, PRIMARY KEY(run_id, event_id), FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS cancel_requests (run_id TEXT PRIMARY KEY, marker_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS run_artifacts (run_id TEXT NOT NULL, name TEXT NOT NULL, path TEXT, artifact_json TEXT NOT NULL, PRIMARY KEY(run_id, name), FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS run_leases (run_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, lease_json TEXT NOT NULL, lease_expires_at TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
            """)

    def safe_run_id(self, run_id: str) -> str:
        value = str(run_id or "").strip()
        if not value or "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"invalid run_id: {run_id}")
        return value

    def run_dir(self, run_id: str) -> Path:
        return self.db_path.parent / self.safe_run_id(run_id)

    def artifact_path(self, run_id: str, name: str) -> Path:
        return self.run_dir(run_id) / name

    def _ensure_run(self, conn: sqlite3.Connection, run_id: str, *, status: str | None = None, error: str | None = None, completed_at: str | None = None, created_at: str | None = None, updated_at: str | None = None) -> None:
        now = now_iso()
        conn.execute("""
            INSERT INTO runs(run_id, status, created_at, updated_at, completed_at, error)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status=COALESCE(excluded.status, runs.status),
                updated_at=excluded.updated_at,
                completed_at=COALESCE(excluded.completed_at, runs.completed_at),
                error=COALESCE(excluded.error, runs.error)
            """, (run_id, status, created_at or now, updated_at or now, completed_at, error))

    def _require_run(self, conn: sqlite3.Connection, run_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return row

    def load_request(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT request_json FROM run_requests WHERE run_id = ?", (safe_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(safe_id)
            return json.loads(row["request_json"])

    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            self._ensure_run(conn, safe_id, status=request.get("status") or "created", created_at=request.get("created_at"), updated_at=request.get("updated_at"))
            conn.execute("INSERT INTO run_requests(run_id, request_json) VALUES(?, ?) ON CONFLICT(run_id) DO UPDATE SET request_json=excluded.request_json", (safe_id, json.dumps(deepcopy(request), ensure_ascii=False, sort_keys=True)))
        return self.artifact_path(safe_id, "agent_request.json")

    def load_report(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT report_json FROM run_reports WHERE run_id = ?", (safe_id,)).fetchone()
            if row is None:
                raise RunNotFoundError(safe_id)
            return json.loads(row["report_json"])

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            self._ensure_run(conn, safe_id, status=report.get("status"), error=report.get("error"), completed_at=report.get("completed_at"), created_at=report.get("created_at"), updated_at=report.get("updated_at"))
            conn.execute("INSERT INTO run_reports(run_id, report_json) VALUES(?, ?) ON CONFLICT(run_id) DO UPDATE SET report_json=excluded.report_json", (safe_id, json.dumps(deepcopy(report), ensure_ascii=False, sort_keys=True)))
        return self.artifact_path(safe_id, "agent_run_report.json")

    def append_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        normalized = normalize_event({**event, "run_id": event.get("run_id") or safe_id})
        with self._connect() as conn:
            self._ensure_run(conn, safe_id, status=normalized.get("status"))
            conn.execute("INSERT OR REPLACE INTO run_events(run_id, event_id, event_type, status, created_at, event_json) VALUES(?, ?, ?, ?, ?, ?)", (safe_id, normalized["event_id"], normalized.get("event_type"), normalized.get("status"), normalized["created_at"], json.dumps(normalized, ensure_ascii=False, sort_keys=True)))
        return normalized

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            self._require_run(conn, safe_id)
            rows = conn.execute("SELECT event_json FROM run_events WHERE run_id = ? ORDER BY created_at, event_id", (safe_id,)).fetchall()
            return [json.loads(row["event_json"]) for row in rows]

    def event_summary(self, run_id: str) -> dict[str, Any]:
        return summarize_agent_events(self.load_events(run_id))

    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT marker_json FROM cancel_requests WHERE run_id = ?", (safe_id,)).fetchone()
            return json.loads(row["marker_json"]) if row else None

    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        safe_id = self.safe_run_id(run_id)
        created_at = marker.get("created_at") or now_iso()
        with self._connect() as conn:
            self._ensure_run(conn, safe_id, status="cancel_requested", updated_at=created_at)
            conn.execute("INSERT INTO cancel_requests(run_id, marker_json, created_at) VALUES(?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET marker_json=excluded.marker_json, created_at=excluded.created_at", (safe_id, json.dumps(deepcopy(marker), ensure_ascii=False, sort_keys=True), created_at))
        return self.artifact_path(safe_id, "cancel_requested.json")

    def cancel_requested(self, run_id: str) -> bool:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM cancel_requests WHERE run_id = ?", (safe_id,)).fetchone() is not None

    def save_artifact(self, run_id: str, name: str, artifact: dict[str, Any], *, path: str | None = None) -> Path:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            self._ensure_run(conn, safe_id)
            conn.execute("INSERT INTO run_artifacts(run_id, name, path, artifact_json) VALUES(?, ?, ?, ?) ON CONFLICT(run_id, name) DO UPDATE SET path=excluded.path, artifact_json=excluded.artifact_json", (safe_id, name, path, json.dumps(deepcopy(artifact), ensure_ascii=False, sort_keys=True)))
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
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs").fetchall()
            for row in rows:
                run_id = row["run_id"]
                report_row = conn.execute("SELECT report_json FROM run_reports WHERE run_id = ?", (run_id,)).fetchone()
                request_row = conn.execute("SELECT request_json FROM run_requests WHERE run_id = ?", (run_id,)).fetchone()
                report = json.loads(report_row["report_json"]) if report_row else {}
                request = json.loads(request_row["request_json"]) if request_row else {}
                fallback = {**request, **report}
                fallback.setdefault("status", row["status"])
                fallback.setdefault("error", row["error"])
                fallback.setdefault("created_at", row["created_at"])
                fallback.setdefault("updated_at", row["updated_at"])
                fallback.setdefault("completed_at", row["completed_at"])
                artifact_count = conn.execute("SELECT COUNT(*) AS count FROM run_artifacts WHERE run_id = ?", (run_id,)).fetchone()["count"]
                fallback.setdefault("artifacts", {"_indexed_count": artifact_count} if artifact_count else {})
                summary = run_summary_from_report(run_id, fallback, run_store=self.metadata())
                if run_summary_matches_filters(summary, status=status, owner_id=owner_id, project_id=project_id, workspace_id=workspace_id, parent_run_id=parent_run_id, query=query):
                    summaries.append(summary)
        page = paginate_run_summaries(summaries, limit=limit, offset=offset, order=order)
        return {**page, "run_store": self.metadata(), "filters": {"status": status, "owner_id": owner_id, "project_id": project_id, "workspace_id": workspace_id, "parent_run_id": parent_run_id, "query": query}}

    def load_worker_lease(self, run_id: str) -> dict[str, Any] | None:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT lease_json FROM run_leases WHERE run_id = ?", (safe_id,)).fetchone()
            return json.loads(row["lease_json"]) if row else None

    def _save_lease(self, conn: sqlite3.Connection, run_id: str, lease: dict[str, Any]) -> None:
        conn.execute("INSERT INTO run_leases(run_id, worker_id, lease_json, lease_expires_at, status, updated_at) VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET worker_id=excluded.worker_id, lease_json=excluded.lease_json, lease_expires_at=excluded.lease_expires_at, status=excluded.status, updated_at=excluded.updated_at", (run_id, lease.get("worker_id"), json.dumps(deepcopy(lease), ensure_ascii=False, sort_keys=True), lease.get("lease_expires_at"), lease.get("status") or "claimed", lease.get("renewed_at") or now_iso()))

    def claim_run(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_run(conn, safe_id)
            row = conn.execute("SELECT lease_json FROM run_leases WHERE run_id = ?", (safe_id,)).fetchone()
            existing = json.loads(row["lease_json"]) if row else None
            if existing and existing.get("status") == "claimed" and not lease_is_expired(existing, at=current) and existing.get("worker_id") != worker_id:
                return {"claimed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "already_claimed", "run_store": self.metadata()}
            lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
            if existing and existing.get("worker_id") == worker_id:
                lease["claimed_at"] = existing.get("claimed_at") or lease["claimed_at"]
            self._save_lease(conn, safe_id, lease)
            return {"claimed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_run(conn, safe_id)
            row = conn.execute("SELECT lease_json FROM run_leases WHERE run_id = ?", (safe_id,)).fetchone()
            existing = json.loads(row["lease_json"]) if row else None
            if not existing or existing.get("status") != "claimed":
                return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
            if existing.get("worker_id") != worker_id:
                return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
            if lease_is_expired(existing, at=current):
                return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "lease_expired", "run_store": self.metadata()}
            lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
            lease["claimed_at"] = existing.get("claimed_at") or lease["claimed_at"]
            self._save_lease(conn, safe_id, lease)
            return {"renewed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def release_run(self, run_id: str, worker_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_run(conn, safe_id)
            row = conn.execute("SELECT lease_json FROM run_leases WHERE run_id = ?", (safe_id,)).fetchone()
            existing = json.loads(row["lease_json"]) if row else None
            if not existing or existing.get("status") != "claimed":
                return {"released": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
            if existing.get("worker_id") != worker_id:
                return {"released": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
            released = {**existing, "status": "released", "released_at": current.isoformat()}
            self._save_lease(conn, safe_id, released)
            return {"released": True, "run_id": safe_id, "worker_id": worker_id, "lease": released, "run_store": self.metadata()}

    def find_expired_leases(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        with self._connect() as conn:
            rows = conn.execute("SELECT lease_json FROM run_leases WHERE status = 'claimed' ORDER BY lease_expires_at").fetchall()
        expired: list[dict[str, Any]] = []
        for row in rows:
            lease = json.loads(row["lease_json"])
            if lease_is_expired(lease, at=current):
                expired.append({**lease, "run_store": self.metadata()})
        return expired

    def status(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        with self._connect() as conn:
            row = self._require_run(conn, safe_id)
            artifact_rows = conn.execute("SELECT name, path, artifact_json FROM run_artifacts WHERE run_id = ? ORDER BY name", (safe_id,)).fetchall()
        try:
            report = self.load_report(safe_id)
        except RunNotFoundError:
            report = {}
        artifacts = report.get("artifacts") or {r["name"]: r["path"] or json.loads(r["artifact_json"]) for r in artifact_rows}
        return {"run_id": safe_id, "status": report.get("status") or row["status"], "error": report.get("error") or row["error"], "created_at": report.get("created_at") or row["created_at"], "updated_at": report.get("updated_at") or row["updated_at"], "completed_at": report.get("completed_at") or row["completed_at"], "cancel_requested": self.cancel_requested(safe_id), "worker_lease": self.load_worker_lease(safe_id), "artifacts": artifacts, "event_summary": self.event_summary(safe_id), "run_store": self.metadata()}

    def metadata(self) -> dict[str, Any]:
        return {"type": "sqlite", "db_path": str(self.db_path)}


def sqlite_run_store(db_path: Path | str) -> SQLiteRunStore:
    return SQLiteRunStore(db_path)
