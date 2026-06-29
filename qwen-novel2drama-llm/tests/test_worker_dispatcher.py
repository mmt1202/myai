from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.run_store import file_run_store
from agent.worker_dispatcher import dispatch_loop, dispatch_one, enqueue_run, list_queue


class WorkerDispatcherTests(unittest.TestCase):
    def test_enqueue_and_list_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            result = enqueue_run(store, {"run_id": "q1", "task": "hello", "approval_policy": "never"})
            self.assertEqual(result["status"], "queued")
            queue = list_queue(store)
            self.assertEqual(queue["total"], 1)
            self.assertEqual(queue["runs"][0]["run_id"], "q1")
            self.assertEqual(store.load_report("q1")["status"], "queued")

    def test_dispatch_one_processes_queued_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            enqueue_run(store, {"run_id": "q1", "task": "hello", "approval_policy": "never", "disable_events": True})
            result = dispatch_one(project_root=PROJECT_ROOT, store=store, worker_id="worker-a")
            self.assertEqual(result["status"], "processed")
            self.assertEqual(result["run_id"], "q1")
            self.assertEqual(store.load_report("q1")["status"], "completed")
            self.assertEqual((store.load_worker_lease("q1") or {}).get("status"), "released")

    def test_dispatch_loop_stops_when_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            enqueue_run(store, {"run_id": "q1", "task": "hello", "approval_policy": "never", "disable_events": True})
            result = dispatch_loop(project_root=PROJECT_ROOT, store=store, worker_id="worker-a", max_runs=3)
            self.assertEqual(result["processed"], 1)
            self.assertEqual(result["results"][-1]["status"], "idle")

    def test_dispatch_dead_letters_after_max_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = file_run_store(Path(tmpdir))
            enqueue_run(store, {"run_id": "q1", "task": "hello", "approval_policy": "never", "queue_attempts": 1, "max_queue_attempts": 1})
            result = dispatch_one(project_root=PROJECT_ROOT, store=store, worker_id="worker-a")
            self.assertEqual(result["status"], "dead_letter")
            report = store.load_report("q1")
            self.assertEqual(report["status"], "failed")
            self.assertEqual((report.get("queue") or {}).get("status"), "dead_letter")


if __name__ == "__main__":
    unittest.main()
