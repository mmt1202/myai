from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from inspect_tool_registry import filter_tools  # noqa: E402
from validate_tool_registry import validate_tool_registry  # noqa: E402


class ToolRegistryTests(unittest.TestCase):
    def test_tool_registry_is_valid(self) -> None:
        registry = json.loads((PROJECT_ROOT / "configs" / "tool_registry.json").read_text(encoding="utf-8"))
        errors = validate_tool_registry(registry, PROJECT_ROOT)
        self.assertEqual(errors, [])

    def test_filter_tools_by_category(self) -> None:
        registry = json.loads((PROJECT_ROOT / "configs" / "tool_registry.json").read_text(encoding="utf-8"))
        context_tools = filter_tools(registry, category="context")
        ids = {tool["id"] for tool in context_tools}
        self.assertIn("build_context_index", ids)
        self.assertIn("read_context_chunk", ids)

    def test_skill_manifest_points_to_tool_registry(self) -> None:
        manifest = json.loads((PROJECT_ROOT / "configs" / "skill_manifest_code_agent.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tool_registry"], "configs/tool_registry.json")
        self.assertEqual(manifest["entrypoint"], "scripts/ai_code_agent.py")

    def test_mcp_manifest_is_planned_only(self) -> None:
        manifest = json.loads((PROJECT_ROOT / "configs" / "mcp_manifest_code_agent.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "planned_manifest_only")
        tool_ids = {tool["registry_tool_id"] for tool in manifest["tools"]}
        self.assertIn("ai_code_agent", tool_ids)


if __name__ == "__main__":
    unittest.main()
