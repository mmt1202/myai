from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.events import AgentEventWriter, read_agent_events, summarize_agent_events, write_agent_event
from agent.runtime import run_agent_once


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
