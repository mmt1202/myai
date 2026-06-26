from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from agent.runtime import add_step, approval_required, create_run, run_agent_once, transition


class AgentRuntimeTests(unittest.TestCase):
    def test_create_run_defaults(self) -> None:
        run = create_run({"task": "demo"})
        self.assertTrue(run["run_id"].startswith("run_"))
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["approval_policy"], "on_cost")

    def test_valid_transition(self) -> None:
        run = create_run({"task": "demo"})
        transition(run, "running")
        self.assertEqual(run["status"], "running")

    def test_invalid_transition_raises(self) -> None:
        run = create_run({"task": "demo"})
        with self.assertRaises(ValueError):
            transition(run, "completed")

    def test_add_step(self) -> None:
        run = create_run({"task": "demo"})
        step = add_step(run, "plan", output_data={"ok": True})
        self.assertEqual(step["type"], "plan")
        self.assertEqual(len(run["steps"]), 1)

    def test_approval_required_for_review(self) -> None:
        run = create_run({"task": "demo", "approval_policy": "on_cost"})
        self.assertTrue(approval_required(run, {"decision": "review"}, {"selected": {}}))

    def test_run_agent_once_completes_local_private_request(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "hello",
                    "route_mode": "balanced",
                    "privacy": {"local_only": True},
                    "input": [{"type": "text", "text": "world"}],
                    "approval_policy": "never",
                },
                output_dir=Path(tmpdir),
            )
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["route_decision"]["selected_model_id"], "local.qwen2_5_1_5b_instruct")
            self.assertTrue((Path(tmpdir) / "usage_ledger.jsonl").exists())

    def test_run_agent_once_waits_for_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "secret task",
                    "route_mode": "smart",
                    "max_sensitivity": "secret",
                    "input": [{"type": "text", "text": "demo"}],
                    "approval_policy": "on_cost",
                },
                output_dir=Path(tmpdir),
            )
            self.assertIn(run["status"], {"waiting_approval", "completed"})
            self.assertIn("route_decision", run)
            self.assertIn("rule_decision", run)

    def test_run_agent_once_executes_provider_dry_run(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "hello provider",
                    "route_mode": "smart",
                    "input": [{"type": "text", "text": "world"}],
                    "approval_policy": "never",
                    "execute_provider": True,
                    "dry_run_provider": True,
                    "base_url": "http://example.test/v1",
                },
                output_dir=Path(tmpdir),
            )
            self.assertEqual(run["status"], "completed")
            self.assertIsNotNone(run["provider_response"])
            self.assertTrue(run["provider_response"]["output"]["dry_run"])
            self.assertTrue((Path(tmpdir) / "provider_response.json").exists())
            self.assertTrue((Path(tmpdir) / "usage_ledger.jsonl").exists())

    def test_run_agent_local_provider_dry_run_succeeds(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "local provider dry run",
                    "route_mode": "balanced",
                    "privacy": {"local_only": True},
                    "approval_policy": "never",
                    "execute_provider": True,
                    "dry_run_provider": True,
                },
                output_dir=Path(tmpdir),
            )
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["provider_response"]["model"]["provider"], "local")
            self.assertTrue(run["provider_response"]["output"]["dry_run"])

    def test_run_agent_executes_safe_skill_loop(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "run safe skill",
                    "route_mode": "balanced",
                    "privacy": {"local_only": True},
                    "approval_policy": "never",
                    "skill_calls": [
                        {
                            "name": "foundation.token_count",
                            "arguments": {"request": {"input": [{"type": "text", "text": "hello"}]}, "expected_output_tokens": 10},
                        }
                    ],
                },
                output_dir=Path(tmpdir),
            )
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["skill_results"][0]["status"], "ok")
            self.assertTrue((Path(tmpdir) / "skill_results.json").exists())

    def test_run_agent_skill_permission_failure_fails_run(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            run = run_agent_once(
                project_root=PROJECT_ROOT,
                request={
                    "task": "denied skill",
                    "route_mode": "balanced",
                    "privacy": {"local_only": True},
                    "approval_policy": "never",
                    "skill_calls": [{"name": "foundation.provider_generate", "arguments": {"request": {}, "registry": {}}}],
                },
                output_dir=Path(tmpdir),
            )
            self.assertEqual(run["status"], "failed")
            self.assertEqual(run["error"], "skill_failed")
            self.assertTrue((Path(tmpdir) / "skill_results.json").exists())


if __name__ == "__main__":
    unittest.main()
