from __future__ import annotations

import json
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent.events import read_agent_events, summarize_agent_events
from agent.runtime import CANCEL_REQUEST_FILENAME, now_iso, save_json

REQUEST_FILENAME = "agent_request.json"
REPORT_FILENAME = "agent_run_report.json"
EVENTS_FILENAME = "events.jsonl"
RUN_CREATED_FILENAME = "agent_run_created.json"
WORKER_LEASE_FILENAME = "worker_lease.json"
DEFAULT_SQLITE_RUN_DB = "runs.sqlite"
RUN_LIST_DEFAULT_LIMIT = 50
RUN_LIST_MAX_LIMIT = 200


class RunStoreError(RuntimeError):
    pass


class RunNotFoundError(FileNotFoundError):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_lease_seconds(value: int | None) -> int:
    if value is None:
        return 60
    return max(1, int(value))


def lease_is_expired(lease: dict[str, Any] | None, *, at: datetime | None = None) -> bool:
    if not lease:
        return True
    expires_at = parse_iso_datetime(lease.get("lease_expires_at"))
    if expires_at is None:
        return True
    return expires_at <= (at or utc_now())


def worker_lease_marker(run_id: str, worker_id: str, *, lease_seconds: int, at: datetime | None = None) -> dict[str, Any]:
    current = at or utc_now()
    seconds = normalize_lease_seconds(lease_seconds)
    return {"run_id": run_id, "worker_id": str(worker_id), "claimed_at": current.isoformat(), "renewed_at": current.isoformat(), "lease_seconds": seconds, "lease_expires_at": (current + timedelta(seconds=seconds)).isoformat(), "status": "claimed"}


def normalize_list_limit(limit: int | None) -> int:
    if limit is None:
        return RUN_LIST_DEFAULT_LIMIT
    return max(1, min(int(limit), RUN_LIST_MAX_LIMIT))


def normalize_list_offset(offset: int | None) -> int:
    if offset is None:
        return 0
    return max(0, int(offset))


def normalize_sort_order(order: str | None) -> str:
    value = str(order or "desc").strip().lower()
    return "asc" if value == "asc" else "desc"


def run_summary_from_report(run_id: str, report: dict[str, Any], *, run_store: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"run_id": run_id, "status": report.get("status"), "error": report.get("error"), "created_at": report.get("created_at"), "updated_at": report.get("updated_at"), "completed_at": report.get("completed_at"), "task": report.get("task"), "owner_id": report.get("owner_id"), "project_id": report.get("project_id"), "workspace_id": report.get("workspace_id"), "parent_run_id": report.get("parent_run_id"), "retry_of": report.get("retry_of"), "resume_of": report.get("resume_of"), "route_mode": report.get("route_mode"), "selected_model_id": (report.get("route_decision") or {}).get("selected_model_id"), "artifact_count": len(report.get("artifacts") or {}), "has_provider_response": bool(report.get("provider_response")), "run_store": run_store or {}}


def run_summary_matches_filters(summary: dict[str, Any], *, status: str | None = None, owner_id: str | None = None, project_id: str | None = None, workspace_id: str | None = None, parent_run_id: str | None = None, query: str | None = None) -> bool:
    filters = {"status": status, "owner_id": owner_id, "project_id": project_id, "workspace_id": workspace_id, "parent_run_id": parent_run_id}
    for key, value in filters.items():
        if value is not None and str(summary.get(key) or "") != str(value):
            return False
    if query:
        needle = query.lower()
        haystack = " ".join(str(summary.get(key) or "") for key in ["run_id", "task", "status", "error", "owner_id", "project_id", "workspace_id", "selected_model_id"]).lower()
        return needle in haystack
    return True


def paginate_run_summaries(runs: list[dict[str, Any]], *, limit: int | None = None, offset: int | None = None, order: str | None = None) -> dict[str, Any]:
    normalized_limit = normalize_list_limit(limit)
    normalized_offset = normalize_list_offset(offset)
    normalized_order = normalize_sort_order(order)
    reverse = normalized_order == "desc"
    sorted_runs = sorted(runs, key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=reverse)
    return {"runs": sorted_runs[normalized_offset : normalized_offset + normalized_limit], "total": len(sorted_runs), "limit": normalized_limit, "offset": normalized_offset, "order": normalized_order}


class RunStore(ABC):
    @abstractmethod
    def safe_run_id(self, run_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def run_dir(self, run_id: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def artifact_path(self, run_id: str, name: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_request(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_report(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def event_summary(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def cancel_requested(self, run_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def save_artifact(self, run_id: str, name: str, artifact: dict[str, Any], *, path: str | None = None) -> Path:
        raise NotImplementedError

    @abstractmethod
    def list_runs(self, *, status: str | None = None, owner_id: str | None = None, project_id: str | None = None, workspace_id: str | None = None, parent_run_id: str | None = None, query: str | None = None, limit: int | None = None, offset: int | None = None, order: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def claim_run(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def release_run(self, run_id: str, worker_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def find_expired_leases(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def status(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError


class FileRunStore(RunStore):
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)

    def safe_run_id(self, run_id: str) -> str:
        value = str(run_id or "").strip()
        if not value or "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"invalid run_id: {run_id}")
        return value

    def run_dir(self, run_id: str) -> Path:
        return self.output_root / self.safe_run_id(run_id)

    def artifact_path(self, run_id: str, name: str) -> Path:
        return self.run_dir(run_id) / name

    def load_json(self, path: Path, default: Any | None = None) -> Any:
        if not path.exists():
            if default is not None:
                return deepcopy(default)
            raise FileNotFoundError(str(path))
        return json.loads(path.read_text(encoding="utf-8"))

    def save_json(self, path: Path, data: dict[str, Any]) -> Path:
        save_json(path, data)
        return path

    def load_request(self, run_id: str) -> dict[str, Any]:
        return self.load_json(self.artifact_path(run_id, REQUEST_FILENAME))

    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, REQUEST_FILENAME), request)

    def load_report(self, run_id: str) -> dict[str, Any]:
        try:
            return self.load_json(self.artifact_path(run_id, REPORT_FILENAME))
        except FileNotFoundError as exc:
            raise RunNotFoundError(self.safe_run_id(run_id)) from exc

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, REPORT_FILENAME), report)

    def load_created_run(self, run_id: str) -> dict[str, Any]:
        return self.load_json(self.artifact_path(run_id, RUN_CREATED_FILENAME))

    def save_created_run(self, run_id: str, run: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, RUN_CREATED_FILENAME), run)

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        return read_agent_events(self.artifact_path(run_id, EVENTS_FILENAME))

    def event_summary(self, run_id: str) -> dict[str, Any]:
        return summarize_agent_events(self.load_events(run_id))

    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        path = self.artifact_path(run_id, CANCEL_REQUEST_FILENAME)
        if not path.exists():
            return None
        return self.load_json(path)

    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, CANCEL_REQUEST_FILENAME), marker)

    def cancel_requested(self, run_id: str) -> bool:
        return self.artifact_path(run_id, CANCEL_REQUEST_FILENAME).exists()

    def save_artifact(self, run_id: str, name: str, artifact: dict[str, Any], *, path: str | None = None) -> Path:
        if path:
            return self.artifact_path(run_id, name)
        return self.save_json(self.artifact_path(run_id, name), artifact)

    def list_runs(self, *, status: str | None = None, owner_id: str | None = None, project_id: str | None = None, workspace_id: str | None = None, parent_run_id: str | None = None, query: str | None = None, limit: int | None = None, offset: int | None = None, order: str | None = None) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        if self.output_root.exists():
            for child in self.output_root.iterdir():
                if not child.is_dir():
                    continue
                try:
                    run_id = self.safe_run_id(child.name)
                    report = self.load_report(run_id)
                except Exception:  # noqa: BLE001
                    continue
                summary = run_summary_from_report(run_id, report, run_store=self.metadata())
                if run_summary_matches_filters(summary, status=status, owner_id=owner_id, project_id=project_id, workspace_id=workspace_id, parent_run_id=parent_run_id, query=query):
                    runs.append(summary)
        page = paginate_run_summaries(runs, limit=limit, offset=offset, order=order)
        return {**page, "run_store": self.metadata(), "filters": {"status": status, "owner_id": owner_id, "project_id": project_id, "workspace_id": workspace_id, "parent_run_id": parent_run_id, "query": query}}

    def load_worker_lease(self, run_id: str) -> dict[str, Any] | None:
        path = self.artifact_path(run_id, WORKER_LEASE_FILENAME)
        if not path.exists():
            return None
        return self.load_json(path)

    def save_worker_lease(self, run_id: str, lease: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, WORKER_LEASE_FILENAME), lease)

    def claim_run(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        self.load_report(safe_id)
        current = now or utc_now()
        existing = self.load_worker_lease(safe_id)
        if existing and existing.get("status") == "claimed" and not lease_is_expired(existing, at=current) and existing.get("worker_id") != worker_id:
            return {"claimed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "already_claimed", "run_store": self.metadata()}
        lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
        self.save_worker_lease(safe_id, lease)
        return {"claimed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        current = now or utc_now()
        existing = self.load_worker_lease(safe_id)
        if not existing or existing.get("status") != "claimed":
            return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
        if existing.get("worker_id") != worker_id:
            return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
        if lease_is_expired(existing, at=current):
            return {"renewed": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "lease_expired", "run_store": self.metadata()}
        lease = worker_lease_marker(safe_id, worker_id, lease_seconds=lease_seconds, at=current)
        lease["claimed_at"] = existing.get("claimed_at") or lease["claimed_at"]
        self.save_worker_lease(safe_id, lease)
        return {"renewed": True, "run_id": safe_id, "worker_id": worker_id, "lease": lease, "run_store": self.metadata()}

    def release_run(self, run_id: str, worker_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        existing = self.load_worker_lease(safe_id)
        if not existing or existing.get("status") != "claimed":
            return {"released": False, "run_id": safe_id, "worker_id": worker_id, "reason": "no_active_lease", "run_store": self.metadata()}
        if existing.get("worker_id") != worker_id:
            return {"released": False, "run_id": safe_id, "worker_id": worker_id, "active_lease": existing, "reason": "worker_mismatch", "run_store": self.metadata()}
        released = {**existing, "status": "released", "released_at": (now or utc_now()).isoformat()}
        self.save_worker_lease(safe_id, released)
        return {"released": True, "run_id": safe_id, "worker_id": worker_id, "lease": released, "run_store": self.metadata()}

    def find_expired_leases(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        expired: list[dict[str, Any]] = []
        if not self.output_root.exists():
            return expired
        for child in self.output_root.iterdir():
            if not child.is_dir():
                continue
            path = child / WORKER_LEASE_FILENAME
            if not path.exists():
                continue
            try:
                lease = self.load_json(path)
            except Exception:  # noqa: BLE001
                continue
            if lease.get("status") == "claimed" and lease_is_expired(lease, at=current):
                expired.append({**lease, "run_store": self.metadata()})
        return expired

    def status(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        report = self.load_report(safe_id)
        return {"run_id": safe_id, "status": report.get("status"), "error": report.get("error"), "created_at": report.get("created_at"), "updated_at": report.get("updated_at"), "completed_at": report.get("completed_at"), "cancel_requested": self.cancel_requested(safe_id), "worker_lease": self.load_worker_lease(safe_id), "artifacts": report.get("artifacts") or {}, "event_summary": self.event_summary(safe_id), "run_store": self.metadata()}

    def metadata(self) -> dict[str, Any]:
        return {"type": "file", "output_root": str(self.output_root)}


def marker_for_cancel(run_id: str, *, reason: str | None = None, requested_by: str | None = None) -> dict[str, Any]:
    return {"created_at": now_iso(), "run_id": FileRunStore(Path(".")).safe_run_id(run_id), "reason": reason or "cancel_requested", "requested_by": requested_by}


def file_run_store(output_root: Path) -> FileRunStore:
    return FileRunStore(output_root)


def default_sqlite_path(output_root: Path) -> Path:
    return Path(output_root) / DEFAULT_SQLITE_RUN_DB


def normalize_run_store_kind(kind: str | None) -> str:
    value = str(kind or "file").strip().lower().replace("_", "-")
    aliases = {"": "file", "file-backed": "file", "file-run-store": "file", "sqlite3": "sqlite", "sqlite-run-store": "sqlite", "postgresql": "postgres", "postgres-run-store": "postgres", "pg": "postgres"}
    return aliases.get(value, value)


def build_run_store(kind: str | None, output_root: Path, *, sqlite_path: Path | str | None = None, postgres_dsn: str | None = None) -> RunStore:
    normalized = normalize_run_store_kind(kind)
    if normalized == "file":
        return file_run_store(output_root)
    if normalized == "sqlite":
        from agent.sqlite_run_store import sqlite_run_store

        return sqlite_run_store(Path(sqlite_path) if sqlite_path else default_sqlite_path(output_root))
    if normalized == "postgres":
        from agent.postgres_run_store import postgres_run_store

        return postgres_run_store(postgres_dsn, output_root=output_root)
    raise ValueError(f"unsupported run store: {kind}")
