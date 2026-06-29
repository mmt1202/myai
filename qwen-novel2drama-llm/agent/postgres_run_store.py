from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.run_store import RunStore, RunStoreError

DEFAULT_POSTGRES_RUN_STORE_DSN_ENV = "FOUNDATION_AGENT_RUN_POSTGRES_DSN"


class PostgresRunStoreUnavailable(RunStoreError):
    pass


class PostgresRunStore(RunStore):
    """Postgres run store scaffold.

    This class intentionally does not open a database connection in core runtime/tests.
    It defines the same RunStore surface and configuration boundary so a later task can
    add a real psycopg/asyncpg implementation behind the contract.
    """

    def __init__(self, dsn: str | None = None, *, output_root: Path | str | None = None, connect: bool = False) -> None:
        self.dsn = dsn or os.environ.get(DEFAULT_POSTGRES_RUN_STORE_DSN_ENV) or ""
        self.output_root = Path(output_root or "outputs/agent_runtime/postgres")
        self.connect = bool(connect)

    def _unavailable(self, operation: str) -> None:
        raise PostgresRunStoreUnavailable(
            f"PostgresRunStore.{operation} is a scaffold only; install the Postgres implementation before using it for runtime operations."
        )

    def safe_run_id(self, run_id: str) -> str:
        value = str(run_id or "").strip()
        if not value or "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"invalid run_id: {run_id}")
        return value

    def run_dir(self, run_id: str) -> Path:
        return self.output_root / self.safe_run_id(run_id)

    def artifact_path(self, run_id: str, name: str) -> Path:
        return self.run_dir(run_id) / name

    def load_request(self, run_id: str) -> dict[str, Any]:
        self._unavailable("load_request")

    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        self._unavailable("save_request")

    def load_report(self, run_id: str) -> dict[str, Any]:
        self._unavailable("load_report")

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        self._unavailable("save_report")

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        self._unavailable("load_events")

    def event_summary(self, run_id: str) -> dict[str, Any]:
        self._unavailable("event_summary")

    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        self._unavailable("load_cancel_request")

    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        self._unavailable("save_cancel_request")

    def cancel_requested(self, run_id: str) -> bool:
        self._unavailable("cancel_requested")

    def save_artifact(self, run_id: str, name: str, artifact: dict[str, Any], *, path: str | None = None) -> Path:
        self._unavailable("save_artifact")

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
        self._unavailable("list_runs")

    def claim_run(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        self._unavailable("claim_run")

    def renew_lease(self, run_id: str, worker_id: str, *, lease_seconds: int = 60, now: datetime | None = None) -> dict[str, Any]:
        self._unavailable("renew_lease")

    def release_run(self, run_id: str, worker_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        self._unavailable("release_run")

    def find_expired_leases(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        self._unavailable("find_expired_leases")

    def status(self, run_id: str) -> dict[str, Any]:
        self._unavailable("status")

    def metadata(self) -> dict[str, Any]:
        return {
            "type": "postgres",
            "dsn_configured": bool(self.dsn),
            "dsn_env": DEFAULT_POSTGRES_RUN_STORE_DSN_ENV,
            "output_root": str(self.output_root),
            "connect_on_init": self.connect,
            "implementation_status": "scaffold",
        }


def postgres_run_store(dsn: str | None = None, *, output_root: Path | str | None = None, connect: bool = False) -> PostgresRunStore:
    return PostgresRunStore(dsn, output_root=output_root, connect=connect)
