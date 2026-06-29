from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.sdk_compat import MCPSessionState, foundation_tool_to_mcp, mcp_call_request, mcp_initialize_request, normalize_mcp_tool, transition_mcp_session


class MCPSDKCompatTests(unittest.TestCase):
    def test_tool_schema_normalization(self) -> None:
        tool = normalize_mcp_tool({"id": "demo", "schema": {"type": "object"}})
        self.assertEqual(tool["name"], "demo")
        self.assertIn("inputSchema", tool)
        converted = foundation_tool_to_mcp({"name": "hello", "parameters": {"type": "object"}})
        self.assertEqual(converted["inputSchema"]["type"], "object")

    def test_request_shapes(self) -> None:
        init = mcp_initialize_request()
        call = mcp_call_request("hello", {"x": 1})
        self.assertEqual(init["method"], "initialize")
        self.assertEqual(call["method"], "tools/call")
        self.assertEqual(call["params"]["arguments"]["x"], 1)

    def test_session_transition(self) -> None:
        state = MCPSessionState(session_id="s1", role="client")
        ready = transition_mcp_session(state, "ready")
        self.assertEqual(ready.status, "ready")
        with self.assertRaises(ValueError):
            transition_mcp_session(ready, "initialized")


if __name__ == "__main__":
    unittest.main()
