from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.run_store import RunNotFoundError, marker_for_cancel
from agent.sqlite_run_store import SQLiteRunStore, sqlite_run_store


class SQLiteRunStoreTests(unittest.TestCase):
    def test_safe_run_id_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteRunStore(Path(tmpdir) / "safe-run-id.db")
            self.assertEqual(store.safe_run_id("demo"), "demo")
            for value in ["", "../x", "a/b", "a\\b"]:
                with self.assertRaises(ValueError):
                    store.safe_run_id(value)

    def test_schema_contains_required_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "runs.sqlite3"
            sqlite_run_store(db_path)
            with sqlite3.connect(db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertGreaterEqual(tables, {"runs", "run_requests", "run_reports", "run_events", "cancel_requests", "run_artifacts"})

    def test_request_and_report_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            request = {"run_id": "demo", "task": "hello"}
            report = {"run_id": "demo", "status": "completed", "artifacts": {"report": "x"}, "completed_at": "2026-01-01T00:00:00+00:00"}
            store.save_request("demo", request)
            store.save_report("demo", report)
            self.assertEqual(store.load_request("demo"), request)
            self.assertEqual(store.load_report("demo"), report)
            self.assertEqual(store.status("demo")["status"], "completed")
            self.assertEqual(store.status("demo")["run_store"]["type"], "sqlite")

    def test_missing_request_or_report_raises_run_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            with self.assertRaises(RunNotFoundError):
                store.load_request("missing")
            with self.assertRaises(RunNotFoundError):
                store.load_report("missing")
            with self.assertRaises(RunNotFoundError):
                store.status("missing")

    def test_events_append_load_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            first = store.append_event("demo", {"event_type": "run_started", "status": "running"})
            second = store.append_event("demo", {"event_type": "run_completed", "status": "completed"})
            events = store.load_events("demo")
            self.assertEqual([event["event_id"] for event in events], [first["event_id"], second["event_id"]])
            summary = store.event_summary("demo")
            self.assertEqual(summary["event_count"], 2)
            self.assertEqual(summary["terminal_event"]["event_type"], "run_completed")

    def test_cancel_marker_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            marker = marker_for_cancel("demo", reason="stop", requested_by="tester")
            store.save_cancel_request("demo", marker)
            self.assertTrue(store.cancel_requested("demo"))
            self.assertEqual(store.load_cancel_request("demo"), marker)
            self.assertTrue(store.status("demo")["cancel_requested"])

    def test_artifact_table_round_trip_visible_in_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            store.save_artifact("demo", "usage.json", {"tokens": 3})
            self.assertEqual(store.status("demo")["artifacts"], {"usage.json": {"tokens": 3}})


if __name__ == "__main__":
    unittest.main()
