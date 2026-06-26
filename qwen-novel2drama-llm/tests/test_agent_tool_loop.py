from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.tool_loop import build_next_provider_request, extract_tool_calls, normalize_tool_call, run_model_tool_loop, tool_result_block


class AgentToolLoopTests(unittest.TestCase):
    def test_normalize_openai_style_tool_call(self) -> None:
        call = normalize_tool_call({"id": "call_1", "type": "function", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[]}}"}})
        self.assertEqual(call["id"], "call_1")
        self.assertEqual(call["name"], "foundation.token_count")
        self.assertIn("request", call["arguments"])

    def test_extract_tool_calls_from_raw_message(self) -> None:
        response = {"output": {"raw_message": {"tool_calls": [{"function": {"name": "foundation.token_count", "arguments": "{}"}}]}}}
        calls = extract_tool_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "foundation.token_count")

    def test_tool_result_block(self) -> None:
        block = tool_result_block({"id": "c1", "name": "foundation.token_count"}, {"status": "ok", "result": {"x": 1}})
        self.assertEqual(block["type"], "tool_result")
        self.assertEqual(block["metadata"]["tool_call_id"], "c1")

    def test_build_next_provider_request_appends_tool_results(self) -> None:
        request = build_next_provider_request(
            {"input": [{"type": "text", "text": "hello"}]},
            "m1",
            [{"tool_call": {"id": "c1", "name": "foundation.token_count"}, "result": {"status": "ok"}}],
        )
        self.assertEqual(request["model_id"], "m1")
        self.assertEqual(request["input"][-1]["type"], "tool_result")

    def test_run_model_tool_loop_executes_one_round_dry_run(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            instances = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            initial = {
                "status": "ok",
                "output": {
                    "raw_message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "foundation.token_count",
                                    "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}",
                                },
                            }
                        ]
                    }
                },
            }
            summary = run_model_tool_loop(
                project_root=PROJECT_ROOT,
                output_dir=Path(tmpdir),
                request={"dry_run_provider": True, "base_url": "http://example.test/v1"},
                foundation_request={"input": [{"type": "text", "text": "hello"}]},
                instances=instances,
                selected_model_id="m1",
                initial_provider_response=initial,
                max_rounds=2,
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["round_count"], 1)
            self.assertTrue((Path(tmpdir) / "model_tool_loop.json").exists())


if __name__ == "__main__":
    unittest.main()
