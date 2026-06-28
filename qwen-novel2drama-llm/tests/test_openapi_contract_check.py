from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_openapi_contract import check_contract, extract_openapi_paths, extract_runtime_routes, missing_tokens


class OpenApiContractCheckTests(unittest.TestCase):
    def test_extract_runtime_routes(self) -> None:
        text = '@app.get("/v1/health")\ndef a(): pass\n@app.post("/v1/chat")\ndef b(): pass\n@app.post("/generate")\ndef c(): pass\n'
        routes = extract_runtime_routes(text)
        self.assertEqual(set(routes), {"/v1/health", "/v1/chat"})
        self.assertEqual(routes["/v1/chat"], {"POST"})

    def test_extract_openapi_paths(self) -> None:
        text = "paths:\n  /v1/health:\n    get:\n  /v1/chat:\n    post:\n  /health:\n    get:\n"
        self.assertEqual(extract_openapi_paths(text), {"/v1/health", "/v1/chat"})

    def test_missing_tokens(self) -> None:
        self.assertEqual(missing_tokens("abc", {"abc", "def"}), ["def"])

    def test_current_contract_is_aligned(self) -> None:
        report = check_contract(PROJECT_ROOT / "inference" / "api_server.py", PROJECT_ROOT / "openapi" / "foundation_api.openapi.yaml")
        self.assertTrue(report["ok"], report)

    def test_detects_openapi_extra_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            api_server = Path(tmpdir) / "api_server.py"
            openapi = Path(tmpdir) / "openapi.yaml"
            api_server.write_text('@app.get("/v1/health")\ndef a(): pass\n', encoding="utf-8")
            openapi.write_text(
                "paths:\n"
                "  /v1/health:\n"
                "    get:\n"
                "  /v1/extra:\n"
                "    get:\n"
                "components:\n"
                "  securitySchemes:\n"
                "    ApiKeyAuth:\n"
                "      name: X-API-Key # X-Workspace-Id\n"
                "  schemas:\n"
                "    FoundationRequest:\n"
                "    FoundationResponse:\n"
                "    ProviderStreamEvent:\n"
                "    ProviderToolCall:\n"
                "    AgentRunRequest:\n"
                "    AgentSkillCall:\n"
                "    AgentLifecycleRequest:\n"
                "    AgentLifecycleResponse:\n"
                "    AgentEvent:\n"
                "    AgentEventsResponse:\n"
                "    execute_provider:\n"
                "    dry_run_provider:\n"
                "    stream:\n"
                "    stream_provider_tool_calls:\n"
                "    incremental_stream_tool_execution:\n"
                "    same_stream_tool_result_injection:\n"
                "    workspace_quota_enabled:\n"
                "    workspace_quota_config_path:\n"
                "    workspace_quota_state_path:\n"
                "    stream_include_usage:\n"
                "    stream_options:\n"
                "    stream_chunk_chars:\n"
                "    provider_stream_delta\n"
                "    provider_stream_tool_call_delta\n"
                "    provider_stream_tool_result\n"
                "    provider_stream_continuation_unsupported\n"
                "    provider_stream_continuation_failed\n"
                "    provider_stream_completed\n"
                "    tool_calls\n"
                "    arguments_json\n"
                "    skill_calls:\n"
                "    enable_model_tool_loop:\n"
                "    max_tool_rounds:\n"
                "    allow_model_tool_provider:\n"
                "    allow_model_tool_write:\n"
                "    approve_model_tools:\n"
                "    fail_on_model_tool_error:\n"
                "    disable_events:\n",
                encoding="utf-8",
            )
            report = check_contract(api_server, openapi)
            self.assertIn("/v1/extra", report["openapi_not_in_runtime"])


if __name__ == "__main__":
    unittest.main()
