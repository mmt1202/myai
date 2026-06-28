from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.events import write_agent_event
from agent.run_store import FileRunStore, RunNotFoundError, file_run_store, marker_for_cancel, run_store_from_config
from agent.runtime import run_agent_once, save_json


class RunStoreTests(unittest.TestCase):
    def test_safe_run_id_rejects_path_traversal(self) -> None:
        store = FileRunStore(Path("/tmp/out"))
        self.assertEqual(store.safe_run_id("demo"), "demo")
        for value in ["", "../x", "a/b", "a\\b"]:
            with self.assertRaises(ValueError):
                store.safe_run_id(value)

    def test_run_store_factory_selects_file_and_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            file_store = run_store_from_config(store_type="file", output_root=output_root)
            sqlite_store = run_store_from_config(store_type="sqlite", output_root=output_root, sqlite_path=output_root / "runs.db")
            self.assertEqual(file_store.metadata()["type"], "file")
            self.assertEqual(sqlite_store.metadata()["type"], "sqlite")
            with self.assertRaises(ValueError):
                run_store_from_config(store_type="unknown", output_root=output_root)  # type: ignore[arg-type]

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
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"},
                output_root / "demo",
            )
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


if __name__ == "__main__":
    unittest.main()
