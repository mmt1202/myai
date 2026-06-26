from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

import inference.api_server as api_server


class FoundationApiServerTests(unittest.TestCase):
    def test_foundation_health(self) -> None:
        result = api_server.foundation_health()
        self.assertEqual(result["status"], "ok")
        self.assertIn("router", result["capabilities"])

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
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
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


if __name__ == "__main__":
    unittest.main()
