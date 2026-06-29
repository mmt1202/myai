from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.events import AgentEventWriter, read_agent_events, summarize_agent_events, write_agent_event
from agent.runtime import run_agent_once
from agent.sqlite_run_store import sqlite_run_store


class AgentEventsTests(unittest.TestCase):
    def test_write_read_and_summarize_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            write_agent_event(path, {"run_id": "r1", "event_type": "run_started", "status": "running"})
            write_agent_event(path, {"run_id": "r1", "event_type": "run_completed", "status": "completed"})
            events = read_agent_events(path)
            summary = summarize_agent_events(events)
            self.assertEqual(len(events), 2)
            self.assertEqual(summary["by_type"]["run_started"], 1)
            self.assertEqual(summary["terminal_event"]["event_type"], "run_completed")

    def test_event_writer_adds_run_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            writer = AgentEventWriter(path, {"run_id": "r1", "session_id": "s1", "owner_id": "u1", "project_id": "p1"})
            writer.emit("route_started", status="running", data={"route_mode": "balanced"})
            event = read_agent_events(path)[0]
            self.assertEqual(event["run_id"], "r1")
            self.assertEqual(event["session_id"], "s1")
            self.assertEqual(event["data"]["route_mode"], "balanced")

    def test_event_writer_appends_to_sqlite_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            path = Path(tmpdir) / "events.jsonl"
            writer = AgentEventWriter(path, {"run_id": "r1", "session_id": "s1", "owner_id": "u1", "project_id": "p1"}, store=store)
            writer.emit("run_started", status="running")
            writer.emit("run_completed", status="completed")

            file_events = read_agent_events(path)
            db_events = store.load_events("r1")
            self.assertEqual([event["event_type"] for event in db_events], ["run_started", "run_completed"])
            self.assertEqual([event["event_id"] for event in db_events], [event["event_id"] for event in file_events])
            self.assertEqual(store.event_summary("r1")["terminal_event"]["event_type"], "run_completed")

    def test_disabled_event_writer_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            writer = AgentEventWriter(path, {"run_id": "r1"}, enabled=False)
            writer.emit("run_started", status="running")
            self.assertFalse(path.exists())

    def test_run_agent_writes_event_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "run"
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "event-test", "task": "hello", "route_mode": "balanced", "approval_policy": "never"},
                output_dir,
            )
            events_path = output_dir / "events.jsonl"
            self.assertEqual(run["status"], "completed")
            self.assertTrue(events_path.exists())
            event_types = {event["event_type"] for event in read_agent_events(events_path)}
            self.assertIn("run_started", event_types)
            self.assertIn("route_completed", event_types)
            self.assertIn("rules_completed", event_types)
            self.assertIn("run_completed", event_types)
            self.assertIn("events", run["artifacts"])
            self.assertGreater(run["event_summary"]["event_count"], 0)

    def test_run_agent_writes_events_to_sqlite_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "run"
            store = sqlite_run_store(Path(tmpdir) / "runs.sqlite3")
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "event-db-test", "task": "hello", "route_mode": "balanced", "approval_policy": "never"},
                output_dir,
                store=store,
            )
            self.assertEqual(run["status"], "completed")
            db_event_types = {event["event_type"] for event in store.load_events("event-db-test")}
            self.assertIn("run_created", db_event_types)
            self.assertIn("run_completed", db_event_types)
            self.assertEqual(run["event_summary"]["event_count"], len(store.load_events("event-db-test")))

    def test_run_agent_can_disable_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "run"
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "event-disabled-test", "task": "hello", "route_mode": "balanced", "approval_policy": "never", "disable_events": True},
                output_dir,
            )
            self.assertEqual(run["status"], "completed")
            self.assertFalse((output_dir / "events.jsonl").exists())
            self.assertEqual(run["event_summary"]["event_count"], 0)


if __name__ == "__main__":
    unittest.main()
