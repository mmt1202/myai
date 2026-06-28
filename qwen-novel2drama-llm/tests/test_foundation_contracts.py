from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FoundationContractsTests(unittest.TestCase):
    def load_json(self, rel_path: str) -> dict:
        return json.loads((PROJECT_ROOT / rel_path).read_text(encoding="utf-8"))

    def test_content_block_schema_supports_core_modalities(self) -> None:
        schema = self.load_json("configs/schemas/content_block_schema.json")
        types = set(schema["properties"]["type"]["enum"])
        self.assertIn("text", types)
        self.assertIn("image", types)
        self.assertIn("video", types)
        self.assertIn("audio", types)
        self.assertIn("file", types)
        self.assertIn("url", types)

    def test_response_envelope_has_usage_cost_and_route(self) -> None:
        schema = self.load_json("configs/schemas/response_envelope_schema.json")
        properties = schema["properties"]
        self.assertIn("usage", properties)
        self.assertIn("cost", properties)
        self.assertIn("route", properties)
        self.assertIn("error", properties)

    def test_model_capability_registry_contains_drama_specialists(self) -> None:
        registry = self.load_json("configs/model_capability_registry.json")
        ids = {item["id"] for item in registry["capabilities"]}
        self.assertIn("drama.story_reasoning", ids)
        self.assertIn("drama.visual_planning", ids)
        self.assertIn("tool.calling", ids)
        self.assertIn("mcp.runtime", ids)

    def test_model_instances_reference_known_capabilities(self) -> None:
        capabilities = self.load_json("configs/model_capability_registry.json")
        known = {item["id"] for item in capabilities["capabilities"]}
        instances = self.load_json("configs/model_instance_registry.json")
        for item in instances["instances"]:
            for capability in item["capabilities"]:
                self.assertIn(capability, known)

    def test_model_router_has_required_route_modes(self) -> None:
        text = (PROJECT_ROOT / "configs/model_router.yaml").read_text(encoding="utf-8")
        for mode in ["smart", "cheap", "balanced", "local_first", "cloud_first", "drama_specialist", "code_specialist"]:
            self.assertIn(f"  {mode}:", text)

    def test_openapi_contains_runtime_foundation_endpoints(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for endpoint in [
            "/v1/health",
            "/v1/chat",
            "/v1/reason",
            "/v1/multimodal/analyze",
            "/v1/route",
            "/v1/token/count",
            "/v1/cost/estimate",
            "/v1/memory/search",
            "/v1/memory/write",
            "/v1/rules/evaluate",
            "/v1/skills/list",
            "/v1/skills/call",
            "/v1/mcp/tools",
            "/v1/mcp/call",
            "/v1/agent/run",
            "/v1/agent/events",
            "/v1/agent/status",
            "/v1/agent/cancel",
            "/v1/agent/retry",
            "/v1/agent/resume",
        ]:
            self.assertIn(endpoint, text)

    def test_openapi_agent_schema_contains_provider_and_skill_loop_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "execute_provider:",
            "dry_run_provider:",
            "skill_calls:",
            "allow_skill_provider:",
            "allow_skill_write:",
            "approve_skills:",
        ]:
            self.assertIn(field, text)

    def test_openapi_contains_provider_stream_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "ProviderStreamEvent:",
            "ProviderToolCall:",
            "provider_stream_started",
            "provider_stream_delta",
            "provider_stream_tool_call_delta",
            "provider_stream_tool_result",
            "provider_stream_continuation_unsupported",
            "provider_stream_continuation_failed",
            "provider_stream_completed",
            "provider_stream_failed",
            "stream_provider_tool_calls:",
            "incremental_stream_tool_execution:",
            "same_stream_tool_result_injection:",
            "stream_include_usage:",
            "stream_options:",
            "stream_chunk_chars:",
            "force_chunked_stream:",
            "tool_calls",
            "arguments_json",
            "text/event-stream",
        ]:
            self.assertIn(field, text)

    def test_openapi_agent_schema_contains_workspace_quota_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "workspace_quota_enabled:",
            "workspace_quota_config_path:",
            "workspace_quota_state_path:",
        ]:
            self.assertIn(field, text)

    def test_openapi_agent_schema_contains_model_tool_loop_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "enable_model_tool_loop:",
            "max_tool_rounds:",
            "allow_model_tool_provider:",
            "allow_model_tool_write:",
            "approve_model_tools:",
            "fail_on_model_tool_error:",
        ]:
            self.assertIn(field, text)

    def test_openapi_agent_schema_contains_event_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "disable_events:",
            "AgentEvent:",
            "AgentEventsResponse:",
            "event_id:",
            "event_type:",
            "since_event_id",
            "text/event-stream",
        ]:
            self.assertIn(field, text)

    def test_openapi_agent_schema_contains_lifecycle_fields(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        for field in [
            "AgentLifecycleRequest:",
            "AgentLifecycleResponse:",
            "new_run_id:",
            "allow_completed:",
            "run_store:",
            "sqlite_path:",
            "cancel_requested:",
            "source_run_id:",
        ]:
            self.assertIn(field, text)

    def test_openapi_contains_api_key_security_scheme(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        self.assertIn("ApiKeyAuth:", text)
        self.assertIn("X-API-Key", text)
        self.assertIn("X-Workspace-Id", text)

    def test_openapi_no_longer_claims_unimplemented_jobs_endpoint(self) -> None:
        text = (PROJECT_ROOT / "openapi/foundation_api.openapi.yaml").read_text(encoding="utf-8")
        self.assertNotIn("/v1/jobs/{job_id}", text)


if __name__ == "__main__":
    unittest.main()
