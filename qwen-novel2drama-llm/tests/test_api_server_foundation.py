from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

import inference.api_server as api_server
from agent.events import write_agent_event
from fastapi.responses import StreamingResponse


class FoundationApiServerTests(unittest.TestCase):
    def test_foundation_health(self) -> None:
        result = api_server.foundation_health()
        self.assertEqual(result["status"], "ok")
        self.assertIn("router", result["capabilities"])
        self.assertIn("agent_events", result["capabilities"])
        self.assertIn("agent_db_events", result["capabilities"])
        self.assertIn("agent_lifecycle", result["capabilities"])
        self.assertIn("agent_run_store", result["capabilities"])
        self.assertIn("agent_run_query", result["capabilities"])
        self.assertIn("provider_stream", result["capabilities"])

    def test_token_count_api(self) -> None:
        result = api_server.token_count_api({"request_id": "r1", "input": [{"type": "text", "text": "hello"}], "expected_output_tokens": 10})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["request_id"], "r1")
        self.assertIn("usage", result)

    def test_route_api_local_only(self) -> None:
        result = api_server.route_api({"route_mode": "balanced", "required_capabilities": ["text.chat"], "privacy": {"local_only": True}, "input": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["route"]["selected_model_id"], "local.qwen2_5_1_5b_instruct")

    def test_rules_evaluate_api(self) -> None:
        result = api_server.rules_evaluate_api({"context": {"request": {"privacy": {"local_only": True}}, "candidate": {"provider": "external"}}})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"]["decision"]["decision"], "deny")

    def test_memory_write_and_search_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = api_server.MEMORY_STORE_PATH
            api_server.MEMORY_STORE_PATH = Path(tmpdir) / "memory.jsonl"
            try:
                write_result = api_server.memory_write_api({"item": {"scope": "project", "project_id": "p1", "content": "角色设定", "tags": ["drama"]}})
                self.assertEqual(write_result["status"], "ok")
                search_result = api_server.memory_search_api({"scope": "project", "project_id": "p1", "query": "角色"})
                self.assertEqual(len(search_result["output"]["items"]), 1)
            finally:
                api_server.MEMORY_STORE_PATH = original

    def test_skills_and_mcp_api(self) -> None:
        skills = api_server.skills_list_api()
        self.assertEqual(skills["status"], "ok")
        self.assertGreater(len(skills["output"]["skills"]), 0)
        mcp = api_server.mcp_tools_api()
        self.assertEqual(mcp["status"], "ok")
        self.assertGreater(len(mcp["output"]["tools"]), 0)

    def test_chat_api_routes_without_provider_execution(self) -> None:
        result = api_server.chat_api({"request_id": "chat1", "input": [{"type": "text", "text": "hello"}]})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"]["provider_execution"], "skipped")
        self.assertIn("provider_execution_skipped", result["warnings"])

    def test_chat_api_streaming_provider_response(self) -> None:
        result = api_server.chat_api({"request_id": "stream1", "route_mode": "local_first", "execute_provider": True, "stream": True, "dry_run_provider": True, "model_path": "/tmp/demo", "input": [{"type": "text", "text": "hello"}]})
        self.assertIsInstance(result, StreamingResponse)
        self.assertEqual(result.media_type, "text/event-stream")

    def test_provider_sse_event_format(self) -> None:
        payload = api_server.provider_sse_event({"chunk_id": "c1", "event_type": "provider_stream_delta", "delta": "hi"})
        self.assertIn("id: c1", payload)
        self.assertIn("event: provider_stream_delta", payload)
        self.assertIn("data:", payload)

    def test_agent_output_dir_uses_request_or_run_id(self) -> None:
        self.assertEqual(api_server.agent_output_dir_for({"request_id": "r1"}).name, "r1")
        self.assertEqual(api_server.agent_output_dir_for({"run_id": "run1"}).name, "run1")
        self.assertEqual(api_server.agent_output_dir_for({}).name, "latest")

    def test_agent_events_api_reads_json_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = api_server.AGENT_OUTPUT_DIR
            api_server.AGENT_OUTPUT_DIR = Path(tmpdir)
            try:
                events_path = api_server.agent_events_path("run1")
                write_agent_event(events_path, {"run_id": "run1", "event_type": "run_started", "status": "running"})
                write_agent_event(events_path, {"run_id": "run1", "event_type": "run_completed", "status": "completed"})
                result = api_server.agent_events_api(run_id="run1")
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["output"]["run_id"], "run1")
                self.assertEqual(result["output"]["events_source"], "run_store")
                self.assertEqual(len(result["output"]["events"]), 2)
                self.assertEqual(result["output"]["summary"]["terminal_event"]["event_type"], "run_completed")
            finally:
                api_server.AGENT_OUTPUT_DIR = original

    def test_agent_lifecycle_status_cancel_retry_resume_and_runs_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = api_server.AGENT_OUTPUT_DIR
            api_server.AGENT_OUTPUT_DIR = Path(tmpdir)
            try:
                run_result = api_server.agent_run_api({"run_id": "demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never", "workspace_id": "w1"})
                self.assertEqual(run_result["status"], "ok")
                status_result = api_server.agent_status_api(run_id="demo")
                self.assertEqual(status_result["status"], "ok")
                self.assertEqual(status_result["output"]["status"], "completed")

                cancel_result = api_server.agent_cancel_api({"run_id": "cancel_me", "reason": "user_requested"})
                self.assertEqual(cancel_result["status"], "ok")
                self.assertEqual(cancel_result["output"]["status"], "cancelled")

                retry_result = api_server.agent_retry_api({"run_id": "demo", "new_run_id": "demo_retry", "overrides": {"task": "retry hello"}})
                self.assertEqual(retry_result["status"], "ok")
                self.assertEqual(retry_result["output"]["new_run_id"], "demo_retry")
                self.assertEqual(retry_result["output"]["run"]["retry_of"], "demo")

                resume_result = api_server.agent_resume_api({"run_id": "demo", "new_run_id": "demo_resume", "allow_completed": True})
                self.assertEqual(resume_result["status"], "ok")
                self.assertEqual(resume_result["output"]["run"]["resume_of"], "demo")

                runs_result = api_server.agent_runs_api(workspace_id="w1", limit=10)
                self.assertEqual(runs_result["status"], "ok")
                self.assertGreaterEqual(runs_result["output"]["total"], 1)
                self.assertIn("demo", [item["run_id"] for item in runs_result["output"]["runs"]])
            finally:
                api_server.AGENT_OUTPUT_DIR = original

    def test_agent_lifecycle_api_uses_sqlite_run_store_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = api_server.AGENT_OUTPUT_DIR
            old_store = os.environ.get("FOUNDATION_AGENT_RUN_STORE")
            old_db = os.environ.get("FOUNDATION_AGENT_RUN_DB")
            api_server.AGENT_OUTPUT_DIR = Path(tmpdir) / "api"
            os.environ["FOUNDATION_AGENT_RUN_STORE"] = "sqlite"
            os.environ["FOUNDATION_AGENT_RUN_DB"] = str(Path(tmpdir) / "runs.sqlite")
            try:
                store = api_server.agent_run_store()
                self.assertEqual(store.metadata()["type"], "sqlite")

                run_result = api_server.agent_run_api({"run_id": "sqlite_demo", "task": "hello", "route_mode": "balanced", "privacy": {"local_only": True}, "approval_policy": "never", "workspace_id": "sqlite_ws"})
                self.assertEqual(run_result["status"], "ok")
                status_result = api_server.agent_status_api(run_id="sqlite_demo")
                self.assertEqual(status_result["status"], "ok")
                self.assertEqual(status_result["output"]["run_store"]["type"], "sqlite")
                self.assertEqual(status_result["output"]["status"], "completed")

                retry_result = api_server.agent_retry_api({"run_id": "sqlite_demo", "new_run_id": "sqlite_retry", "overrides": {"task": "retry sqlite"}})
                self.assertEqual(retry_result["status"], "ok")
                self.assertEqual(api_server.agent_status_api(run_id="sqlite_retry")["output"]["status"], "completed")

                runs_result = api_server.agent_runs_api(workspace_id="sqlite_ws", query="hello")
                self.assertEqual(runs_result["status"], "ok")
                self.assertEqual(runs_result["output"]["run_store"]["type"], "sqlite")
                self.assertIn("sqlite_demo", [item["run_id"] for item in runs_result["output"]["runs"]])

                events_file = api_server.agent_events_path("sqlite_demo")
                if events_file.exists():
                    events_file.unlink()
                events_result = api_server.agent_events_api(run_id="sqlite_demo")
                self.assertEqual(events_result["status"], "ok")
                self.assertEqual(events_result["output"]["run_store"]["type"], "sqlite")
                self.assertEqual(events_result["output"]["events_source"], "run_store")
                event_types = {event["event_type"] for event in events_result["output"]["events"]}
                self.assertIn("run_started", event_types)
                self.assertIn("run_completed", event_types)
            finally:
                api_server.AGENT_OUTPUT_DIR = original_dir
                if old_store is None:
                    os.environ.pop("FOUNDATION_AGENT_RUN_STORE", None)
                else:
                    os.environ["FOUNDATION_AGENT_RUN_STORE"] = old_store
                if old_db is None:
                    os.environ.pop("FOUNDATION_AGENT_RUN_DB", None)
                else:
                    os.environ["FOUNDATION_AGENT_RUN_DB"] = old_db

    def test_agent_lifecycle_missing_run_returns_failed_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = api_server.AGENT_OUTPUT_DIR
            api_server.AGENT_OUTPUT_DIR = Path(tmpdir)
            try:
                result = api_server.agent_status_api(run_id="missing")
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"]["code"], "agent_run_not_found")
            finally:
                api_server.AGENT_OUTPUT_DIR = original

    def test_sse_event_format(self) -> None:
        payload = api_server.sse_event({"event_id": "e1", "event_type": "run_started", "status": "running"})
        self.assertIn("id: e1", payload)
        self.assertIn("event: run_started", payload)
        self.assertIn("data:", payload)


if __name__ == "__main__":
    unittest.main()
