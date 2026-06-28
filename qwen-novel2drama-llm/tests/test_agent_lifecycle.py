from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.lifecycle import cancel_run, resume_run, retry_run, status_run
from agent.runtime import run_agent_once, save_json


class AgentLifecycleTests(unittest.TestCase):
    def test_status_reads_report_and_events(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_root = Path(tmpdir)
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"},
                output_root / "demo",
            )
            self.assertEqual(run["status"], "completed")
            status = status_run(output_root, "demo")
            self.assertEqual(status["run_id"], "demo")
            self.assertEqual(status["status"], "completed")
            self.assertIn("event_summary", status)

    def test_cancel_existing_running_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_root = Path(tmpdir)
            run_dir = output_root / "demo"
            save_json(run_dir / "agent_run_report.json", {"run_id": "demo", "status": "running", "steps": [], "artifacts": {}})
            result = cancel_run(output_root, "demo", reason="user_requested", requested_by="tester")
            self.assertEqual(result["status"], "cancelled")
            self.assertTrue((run_dir / "cancel_requested.json").exists())
            report = status_run(output_root, "demo")
            self.assertEqual(report["status"], "cancelled")
            self.assertTrue(report["cancel_requested"])

    def test_runtime_honors_preexisting_cancel_marker(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_dir = Path(tmpdir) / "demo"
            save_json(output_dir / "cancel_requested.json", {"reason": "stop_before_start"})
            run = run_agent_once(
                PROJECT_ROOT,
                {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"},
                output_dir,
            )
            self.assertEqual(run["status"], "cancelled")
            self.assertEqual(run["error"], "cancelled")
            self.assertIn("cancel_request", run["artifacts"])

    def test_retry_run_uses_original_request_and_new_run_id(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_root = Path(tmpdir)
            run_agent_once(
                PROJECT_ROOT,
                {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"},
                output_root / "demo",
            )
            result = retry_run(project_root=PROJECT_ROOT, output_root=output_root, run_id="demo", new_run_id="demo_retry", overrides={"task": "retry hello"})
            self.assertEqual(result["new_run_id"], "demo_retry")
            self.assertEqual(result["run"]["retry_of"], "demo")
            self.assertEqual(result["run"]["status"], "completed")
            self.assertTrue((output_root / "demo_retry" / "agent_request.json").exists())

    def test_resume_failed_run_with_overrides(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_root = Path(tmpdir)
            failed = run_agent_once(
                PROJECT_ROOT,
                {
                    "run_id": "failed_demo",
                    "task": "denied skill",
                    "route_mode": "balanced",
                    "privacy": {"local_only": True},
                    "approval_policy": "never",
                    "skill_calls": [{"name": "foundation.provider_generate", "arguments": {"request": {}, "registry": {}}}],
                },
                output_root / "failed_demo",
            )
            self.assertEqual(failed["status"], "failed")
            result = resume_run(project_root=PROJECT_ROOT, output_root=output_root, run_id="failed_demo", new_run_id="failed_demo_resume", overrides={"skill_calls": []})
            self.assertEqual(result["source_status"], "failed")
            self.assertEqual(result["run"]["resume_of"], "failed_demo")
            self.assertEqual(result["run"]["status"], "completed")

    def test_resume_completed_requires_allow_completed(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_root = Path(tmpdir)
            run_agent_once(
                PROJECT_ROOT,
                {"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never"},
                output_root / "demo",
            )
            with self.assertRaises(ValueError):
                resume_run(project_root=PROJECT_ROOT, output_root=output_root, run_id="demo", new_run_id="demo_resume")


if __name__ == "__main__":
    unittest.main()
