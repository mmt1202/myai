from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.events import write_agent_event
from agent.postgres_run_store import PostgresRunStore, PostgresRunStoreUnavailable
from agent.run_store import FileRunStore, RunNotFoundError, build_run_store, default_sqlite_path, file_run_store, marker_for_cancel, normalize_run_store_kind
from agent.runtime import run_agent_once, save_json
from agent.sqlite_run_store import SQLiteRunStore


class RunStoreTests(unittest.TestCase):
    def test_safe_run_id_rejects_path_traversal(self) -> None:
        store = FileRunStore(Path("/tmp/out"))
        self.assertEqual(store.safe_run_id("demo"), "demo")
        for value in ["", "../x", "a/b", "a\\b"]:
            with self.assertRaises(ValueError):
                store.safe_run_id(value)

    def test_file_run_store_reads_and_writes_core_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            request = {"run_id": "demo", "task": "hello"}
            report = {"run_id": "demo", "status": "running", "artifacts": {}}
            store.save_request("demo", request)
            store.save_report("demo", report)
            self.assertEqual(store.load_request("demo"), request)
            self.assertEqual(store.load_report("demo"), report)
            self.assertTrue(store.artifact_path("demo", "agent_request.json").exists())

    def test_missing_report_raises_run_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            with self.assertRaises(RunNotFoundError):
                store.load_report("missing")

    def test_file_run_store_events_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            store.save_report("demo", {"run_id": "demo", "status": "completed", "artifacts": {"report": "x"}})
            write_agent_event(store.artifact_path("demo", "events.jsonl"), {"run_id": "demo", "event_type": "run_started", "status": "running"})
            write_agent_event(store.artifact_path("demo", "events.jsonl"), {"run_id": "demo", "event_type": "run_completed", "status": "completed"})
            status = store.status("demo")
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["event_summary"]["terminal_event"]["event_type"], "run_completed")
            self.assertEqual(status["run_store"]["type"], "file")

    def test_file_run_store_lists_and_filters_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            store.save_report("a", {"run_id": "a", "status": "completed", "task": "alpha task", "workspace_id": "w1", "owner_id": "u1", "updated_at": "2026-01-02T00:00:00+00:00", "artifacts": {}})
            store.save_report("b", {"run_id": "b", "status": "failed", "task": "beta task", "workspace_id": "w2", "owner_id": "u1", "updated_at": "2026-01-03T00:00:00+00:00", "artifacts": {}})
            store.save_report("c", {"run_id": "c", "status": "completed", "task": "gamma task", "workspace_id": "w1", "owner_id": "u2", "updated_at": "2026-01-01T00:00:00+00:00", "artifacts": {}})

            all_runs = store.list_runs()
            self.assertEqual(all_runs["total"], 3)
            self.assertEqual([item["run_id"] for item in all_runs["runs"]], ["b", "a", "c"])

            completed = store.list_runs(status="completed", workspace_id="w1", order="asc")
            self.assertEqual([item["run_id"] for item in completed["runs"]], ["c", "a"])

            queried = store.list_runs(query="beta")
            self.assertEqual(queried["total"], 1)
            self.assertEqual(queried["runs"][0]["run_id"], "b")

            page = store.list_runs(limit=1, offset=1)
            self.assertEqual(page["limit"], 1)
            self.assertEqual(page["offset"], 1)
            self.assertEqual(len(page["runs"]), 1)

    def test_file_run_store_worker_lease_claim_renew_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            store.save_report("demo", {"run_id": "demo", "status": "running", "artifacts": {}})
            at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

            claim = store.claim_run("demo", "worker-a", lease_seconds=30, now=at)
            self.assertTrue(claim["claimed"])
            self.assertEqual(claim["lease"]["worker_id"], "worker-a")
            self.assertEqual(store.status("demo")["worker_lease"]["worker_id"], "worker-a")

            blocked = store.claim_run("demo", "worker-b", lease_seconds=30, now=at + timedelta(seconds=10))
            self.assertFalse(blocked["claimed"])
            self.assertEqual(blocked["reason"], "already_claimed")

            renewed = store.renew_lease("demo", "worker-a", lease_seconds=60, now=at + timedelta(seconds=10))
            self.assertTrue(renewed["renewed"])
            self.assertEqual(renewed["lease"]["claimed_at"], claim["lease"]["claimed_at"])

            released = store.release_run("demo", "worker-a", now=at + timedelta(seconds=20))
            self.assertTrue(released["released"])
            self.assertEqual(store.load_worker_lease("demo")["status"], "released")

    def test_file_run_store_expired_lease_can_be_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            store.save_report("demo", {"run_id": "demo", "status": "running", "artifacts": {}})
            at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            store.claim_run("demo", "worker-a", lease_seconds=5, now=at)
            expired = store.find_expired_leases(now=at + timedelta(seconds=6))
            self.assertEqual(len(expired), 1)
            self.assertEqual(expired[0]["run_id"], "demo")
            reclaimed = store.claim_run("demo", "worker-b", lease_seconds=30, now=at + timedelta(seconds=6))
            self.assertTrue(reclaimed["claimed"])
            self.assertEqual(reclaimed["lease"]["worker_id"], "worker-b")

    def test_cancel_marker_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            marker = marker_for_cancel("demo", reason="stop", requested_by="tester")
            store.save_cancel_request("demo", marker)
            self.assertTrue(store.cancel_requested("demo"))
            self.assertEqual(store.load_cancel_request("demo")["reason"], "stop")

    def test_file_run_store_is_compatible_with_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            run = run_agent_once(PROJECT_ROOT, {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"}, output_root / "demo")
            self.assertEqual(run["status"], "completed")
            store = file_run_store(output_root)
            self.assertEqual(store.load_request("demo")["task"], "hello")
            self.assertEqual(store.status("demo")["status"], "completed")

    def test_store_status_reflects_cancel_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            run_dir = output_root / "demo"
            save_json(run_dir / "agent_run_report.json", {"run_id": "demo", "status": "running", "artifacts": {}})
            store = file_run_store(output_root)
            store.save_cancel_request("demo", marker_for_cancel("demo"))
            self.assertTrue(store.status("demo")["cancel_requested"])

    def test_normalize_run_store_kind_aliases(self) -> None:
        self.assertEqual(normalize_run_store_kind(None), "file")
        self.assertEqual(normalize_run_store_kind("file-backed"), "file")
        self.assertEqual(normalize_run_store_kind("sqlite3"), "sqlite")
        self.assertEqual(normalize_run_store_kind("sqlite_run_store"), "sqlite")
        self.assertEqual(normalize_run_store_kind("postgresql"), "postgres")
        self.assertEqual(normalize_run_store_kind("pg"), "postgres")

    def test_build_run_store_selects_file_sqlite_or_postgres(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            self.assertIsInstance(build_run_store("file", output_root), FileRunStore)
            sqlite = build_run_store("sqlite", output_root, sqlite_path=output_root / "runs.db")
            self.assertIsInstance(sqlite, SQLiteRunStore)
            self.assertEqual(sqlite.metadata()["db_path"], str(output_root / "runs.db"))
            postgres = build_run_store("postgres", output_root, postgres_dsn="configured")
            self.assertIsInstance(postgres, PostgresRunStore)
            self.assertEqual(postgres.metadata()["type"], "postgres")
            self.assertEqual(postgres.metadata()["implementation_status"], "persistence_v1")
            self.assertTrue(postgres.metadata()["dsn_configured"])

    def test_postgres_run_store_core_contract_without_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PostgresRunStore("configured", output_root=Path(tmpdir))
            self.assertEqual(store.safe_run_id("demo"), "demo")
            self.assertEqual(store.run_dir("demo"), Path(tmpdir) / "demo")
            self.assertEqual(store.metadata()["implementation_status"], "persistence_v1")

    def test_postgres_run_store_missing_dsn_fails_explicitly(self) -> None:
        old = os.environ.pop("FOUNDATION_AGENT_RUN_POSTGRES_DSN", None)
        try:
            store = PostgresRunStore(output_root=Path("/tmp/out"))
            self.assertFalse(store.metadata()["dsn_configured"])
            with self.assertRaises(PostgresRunStoreUnavailable):
                store.list_runs()
        finally:
            if old is not None:
                os.environ["FOUNDATION_AGENT_RUN_POSTGRES_DSN"] = old

    def test_postgres_run_store_reads_dsn_from_env(self) -> None:
        old = os.environ.get("FOUNDATION_AGENT_RUN_POSTGRES_DSN")
        os.environ["FOUNDATION_AGENT_RUN_POSTGRES_DSN"] = "configured-from-env"
        try:
            store = PostgresRunStore(output_root=Path("/tmp/out"))
            self.assertTrue(store.metadata()["dsn_configured"])
        finally:
            if old is None:
                os.environ.pop("FOUNDATION_AGENT_RUN_POSTGRES_DSN", None)
            else:
                os.environ["FOUNDATION_AGENT_RUN_POSTGRES_DSN"] = old

    def test_build_run_store_uses_default_sqlite_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            store = build_run_store("sqlite", output_root)
            self.assertEqual(store.metadata()["db_path"], str(default_sqlite_path(output_root)))

    def test_build_run_store_rejects_unknown_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                build_run_store("unknown", Path(tmpdir))


if __name__ == "__main__":
    unittest.main()
