from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

import inference.api_server as api_server


class ApiSmokeTests(unittest.TestCase):
    def test_health_and_ready(self) -> None:
        self.assertEqual(api_server.health()["status"], "ok")
        self.assertEqual(api_server.foundation_health()["status"], "ok")
        self.assertIn(api_server.readiness_api()["status"], {"ok", "degraded"})
        self.assertIn(api_server.deep_health_api()["status"], {"ok", "degraded"})

    def test_usage_route_and_cost(self) -> None:
        body = {"request_id": "smoke", "input": [{"type": "text", "text": "hello"}], "expected_output_tokens": 16, "privacy": {"local_only": True}}
        self.assertEqual(api_server.token_count_api(body)["status"], "ok")
        self.assertEqual(api_server.route_api({**body, "required_capabilities": ["text.chat"]})["status"], "ok")
        self.assertEqual(api_server.cost_estimate_api({**body, "model_id": "local.qwen2_5_1_5b_instruct"})["status"], "ok")

    def test_memory_skills_and_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = api_server.MEMORY_STORE_PATH
            api_server.MEMORY_STORE_PATH = Path(tmpdir) / "memory.jsonl"
            try:
                self.assertEqual(api_server.memory_write_api({"item": {"scope": "project", "project_id": "p1", "content": "hello memory"}})["status"], "ok")
                self.assertEqual(api_server.memory_search_api({"scope": "project", "project_id": "p1", "query": "hello"})["status"], "ok")
            finally:
                api_server.MEMORY_STORE_PATH = original
        skills = api_server.skills_list_api(category="drama_specialist")
        self.assertEqual(skills["status"], "ok")
        self.assertGreaterEqual(len(skills["output"]["skills"]), 1)
        self.assertEqual(api_server.mcp_tools_api()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
