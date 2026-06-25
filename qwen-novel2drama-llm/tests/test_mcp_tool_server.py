from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from mcp_tool_server import ToolServer, command_for_tool, input_schema, load_profile


class McpToolServerTests(unittest.TestCase):
    def make_server(self, profile: str = "planning") -> ToolServer:
        return ToolServer(
            project_root=PROJECT_ROOT,
            registry_path=PROJECT_ROOT / "configs" / "tool_registry.json",
            mcp_manifest_path=PROJECT_ROOT / "configs" / "mcp_manifest_code_agent.json",
            profiles_path=PROJECT_ROOT / "configs" / "tool_permission_profiles.json",
            profile_id=profile,
            audit_log=None,
            timeout=10,
        )

    def test_load_profile(self) -> None:
        profiles = json.loads((PROJECT_ROOT / "configs" / "tool_permission_profiles.json").read_text(encoding="utf-8"))
        self.assertEqual(load_profile(profiles, "readonly")["id"], "readonly")

    def test_list_tools_contains_agent_run(self) -> None:
        names = {tool["name"] for tool in self.make_server("planning").list_tools()}
        self.assertIn("agent.run", names)

    def test_input_schema_marks_boolean(self) -> None:
        schema = input_schema({"inputs": ["dry_run", "task"]})
        self.assertEqual(schema["properties"]["dry_run"]["type"], "boolean")
        self.assertEqual(schema["properties"]["task"]["type"], "string")

    def test_command_for_tool_maps_args(self) -> None:
        command = command_for_tool(PROJECT_ROOT, {"script": "scripts/run_agent_workflow.py"}, {"task": "demo", "output_dir": "out", "execute_tests": True})
        self.assertIn("--task", command)
        self.assertIn("--output-dir", command)
        self.assertIn("--execute-tests", command)

    def test_readonly_profile_blocks_write_tool_call(self) -> None:
        with self.assertRaises(PermissionError):
            self.make_server("readonly").call_tool("agent.run", {"task": "demo"})

    def test_jsonrpc_tools_list(self) -> None:
        response = self.make_server("planning").handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])


if __name__ == "__main__":
    unittest.main()
