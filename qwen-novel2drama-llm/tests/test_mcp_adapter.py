from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.adapter import FoundationMCPAdapter, skill_to_mcp_tool
from skills.registry import load_json


class MCPAdapterTests(unittest.TestCase):
    def make_adapter(self, **kwargs) -> FoundationMCPAdapter:
        return FoundationMCPAdapter(PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json", **kwargs)

    def test_skill_to_mcp_tool(self) -> None:
        registry = load_json(PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json")
        tool = skill_to_mcp_tool(registry["skills"][0])
        self.assertIn("name", tool)
        self.assertIn("inputSchema", tool)
        self.assertIn("annotations", tool)

    def test_list_tools_contains_token_count(self) -> None:
        tools = self.make_adapter().list_tools()["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("foundation.token_count", names)

    def test_call_safe_tool(self) -> None:
        result = self.make_adapter().call_tool(
            "foundation.token_count",
            {"request": {"input": [{"type": "text", "text": "hello"}]}, "expected_output_tokens": 10},
        )
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["status"], "ok")

    def test_provider_tool_denied_without_permission(self) -> None:
        result = self.make_adapter().call_tool("foundation.provider_generate", {"request": {}, "registry": {}})
        self.assertTrue(result["isError"])

    def test_resources_and_prompts(self) -> None:
        adapter = self.make_adapter()
        self.assertIn("resources", adapter.list_resources())
        self.assertIn("prompts", adapter.list_prompts())
        prompt = adapter.get_prompt("foundation_task", {"task": "demo"})
        self.assertIn("messages", prompt)

    def test_jsonrpc_tools_list(self) -> None:
        response = self.make_adapter().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])

    def test_audit_log(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            audit_log = Path(tmpdir) / "mcp.jsonl"
            adapter = self.make_adapter(audit_log=audit_log)
            adapter.handle({"jsonrpc": "2.0", "id": 1, "method": "ping"})
            self.assertTrue(audit_log.exists())


if __name__ == "__main__":
    unittest.main()
