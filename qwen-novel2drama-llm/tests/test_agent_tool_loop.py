from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.tool_loop import (
    build_next_provider_request,
    complete_partial_tool_call,
    extract_tool_calls,
    generate_provider_round,
    incremental_result_map,
    maybe_execute_incremental_tool_call,
    normalize_tool_call,
    provider_response_from_stream_chunks,
    run_model_tool_loop,
    tool_result_block,
)


class AgentToolLoopTests(unittest.TestCase):
    def load_skill_registry(self) -> dict:
        return json.loads((PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json").read_text(encoding="utf-8"))

    def stream_tool_call_chunk(self) -> dict:
        return {
            "chunk_id": "chunk_tool_1",
            "event_type": "provider_stream_tool_call_delta",
            "metadata": {
                "tool_call_partial": {
                    "id": "call_1",
                    "index": 0,
                    "type": "function",
                    "function": {
                        "name": "foundation.token_count",
                        "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}",
                    },
                }
            },
        }

    def test_normalize_openai_style_tool_call(self) -> None:
        call = normalize_tool_call({"id": "call_1", "type": "function", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[]}}"}})
        self.assertEqual(call["id"], "call_1")
        self.assertEqual(call["name"], "foundation.token_count")
        self.assertIn("request", call["arguments"])

    def test_normalize_reconstructed_tool_call_prefers_arguments_json(self) -> None:
        call = normalize_tool_call({"id": "call_1", "type": "function", "function": {"name": "foundation.token_count", "arguments": ""}, "arguments_json": {"request": {"input": []}}})
        self.assertEqual(call["name"], "foundation.token_count")
        self.assertEqual(call["arguments"], {"request": {"input": []}})

    def test_extract_tool_calls_from_raw_message(self) -> None:
        response = {"output": {"raw_message": {"tool_calls": [{"function": {"name": "foundation.token_count", "arguments": "{}"}}]}}}
        calls = extract_tool_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "foundation.token_count")

    def test_extract_tool_calls_from_stream_completed_output(self) -> None:
        response = {"output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{}"}}]}}
        calls = extract_tool_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["id"], "call_1")

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

    def test_provider_response_from_stream_chunks_reuses_completed_output(self) -> None:
        response = provider_response_from_stream_chunks(
            [
                {"event_type": "provider_stream_started", "request_id": "r1"},
                {"event_type": "provider_stream_tool_call_delta", "metadata": {"tool_call_partial": {}}},
                {
                    "event_type": "provider_stream_completed",
                    "request_id": "r1",
                    "model": {"model_id": "m1"},
                    "usage": {"total_tokens": 3},
                    "output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{}"}}]},
                    "metadata": {"tool_call_count": 1},
                },
            ]
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["stream"]["tool_call_count"], 1)
        self.assertEqual(extract_tool_calls(response)[0]["name"], "foundation.token_count")

    def test_complete_partial_tool_call_requires_complete_json(self) -> None:
        incomplete = {"event_type": "provider_stream_tool_call_delta", "metadata": {"tool_call_partial": {"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{\"request\":"}}}}}
        self.assertIsNone(complete_partial_tool_call(incomplete))
        complete = complete_partial_tool_call(self.stream_tool_call_chunk())
        self.assertIsNotNone(complete)
        self.assertEqual(complete["name"], "foundation.token_count")

    def test_maybe_execute_incremental_tool_call_executes_once(self) -> None:
        registry = self.load_skill_registry()
        executed: set[str] = set()
        first = maybe_execute_incremental_tool_call(self.stream_tool_call_chunk(), registry, executed)
        second = maybe_execute_incremental_tool_call(self.stream_tool_call_chunk(), registry, executed)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertTrue(first["executed_while_streaming"])
        self.assertEqual(first["result"]["status"], "ok")

    def test_incremental_result_map(self) -> None:
        mapped = incremental_result_map({"incremental_tool_results": [{"tool_call": {"id": "call_1"}, "result": {"status": "ok", "tool_call_id": "call_1"}}]})
        self.assertEqual(mapped["call_1"]["status"], "ok")

    def test_generate_provider_round_stream_dry_run_saves_chunks(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            instances = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            path = Path(tmpdir) / "chunks.jsonl"
            response = generate_provider_round(
                {"request_id": "r1", "model_id": "m1", "dry_run_provider": True, "input": [{"type": "text", "text": "hello"}]},
                instances,
                selected_model_id="m1",
                base_url="http://example.test/v1",
                stream=True,
                stream_chunks_path=path,
            )
            self.assertEqual(response["status"], "ok")
            self.assertTrue(path.exists())
            self.assertTrue(response["stream"]["completed"])

    def test_generate_provider_round_incremental_tool_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            instances = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            completed = {
                "chunk_id": "chunk_done",
                "event_type": "provider_stream_completed",
                "request_id": "r1",
                "model": {"model_id": "m1"},
                "output": {"tool_calls": [{"id": "call_1", "function": {"name": "foundation.token_count", "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}"}}]},
                "metadata": {"tool_call_count": 1},
            }
            chunks = [{"event_type": "provider_stream_started", "request_id": "r1"}, self.stream_tool_call_chunk(), completed]
            results_path = Path(tmpdir) / "incremental.json"
            with patch("agent.tool_loop.stream_generate_with_registry", return_value=iter(chunks)):
                response = generate_provider_round(
                    {"request_id": "r1", "model_id": "m1", "input": [{"type": "text", "text": "hello"}]},
                    instances,
                    selected_model_id="m1",
                    stream=True,
                    incremental_tools=True,
                    registry=self.load_skill_registry(),
                    incremental_tool_results_path=results_path,
                )
            self.assertEqual(response["status"], "ok")
            self.assertEqual(response["stream"]["incremental_tool_result_count"], 1)
            self.assertEqual(response["incremental_tool_results"][0]["result"]["status"], "ok")
            self.assertTrue(results_path.exists())

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

    def test_run_model_tool_loop_can_use_stream_for_followup_round(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            instances = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            initial = {
                "status": "ok",
                "output": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "foundation.token_count",
                                "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}",
                            },
                        }
                    ]
                },
            }
            summary = run_model_tool_loop(
                project_root=PROJECT_ROOT,
                output_dir=Path(tmpdir),
                request={"dry_run_provider": True, "base_url": "http://example.test/v1", "stream_provider_tool_calls": True},
                foundation_request={"input": [{"type": "text", "text": "hello"}]},
                instances=instances,
                selected_model_id="m1",
                initial_provider_response=initial,
                max_rounds=2,
            )
            self.assertEqual(summary["status"], "ok")
            self.assertTrue(summary["stream_provider_tool_calls"])
            self.assertTrue((Path(tmpdir) / "model_tool_loop_stream_round_1.jsonl").exists())
            self.assertEqual(summary["rounds"][0]["provider_response"]["stream"]["completed"], True)

    def test_run_model_tool_loop_reuses_incremental_tool_result(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            instances = {"instances": [{"id": "m1", "aliases": [], "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": "demo"}]}
            initial = {
                "status": "ok",
                "output": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "foundation.token_count",
                                "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]},\"expected_output_tokens\":10}",
                            },
                        }
                    ]
                },
                "incremental_tool_results": [
                    {
                        "tool_call": {"id": "call_1", "name": "foundation.token_count"},
                        "result": {"tool_call_id": "call_1", "name": "foundation.token_count", "status": "ok", "result": {"status": "ok"}},
                    }
                ],
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
            self.assertEqual(summary["rounds"][0]["tool_results"][0]["result"]["source"], "incremental_stream")


if __name__ == "__main__":
    unittest.main()
