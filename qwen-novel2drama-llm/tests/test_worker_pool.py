from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.run_store import file_run_store
from agent.worker_dispatcher import enqueue_run
from agent.worker_pool import worker_pool_iteration, worker_pool_loop


class WorkerPoolTests(unittest.TestCase):
    def test_worker_pool_iteration_processes_queued_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "queue"
            store = file_run_store(output_root)
            enqueue_run(store, {"run_id": "q1", "task": "hello", "approval_policy": "never", "privacy": {"local_only": True}})
            result = worker_pool_iteration(project_root=PROJECT_ROOT, output_root=output_root, worker_count=2, max_runs_per_worker=1)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["processed"], 1)
            self.assertEqual(len(result["workers"]), 2)

    def test_worker_pool_loop_stops_after_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = worker_pool_loop(project_root=PROJECT_ROOT, output_root=Path(tmpdir) / "queue", poll_seconds=0, max_iterations=3, max_idle_iterations=1)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["processed"], 0)
            self.assertEqual(result["idle_iterations"], 1)


if __name__ == "__main__":
    unittest.main()
