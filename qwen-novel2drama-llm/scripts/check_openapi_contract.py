from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROUTE_PATTERN = re.compile(r"@app\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']")
OPENAPI_PATH_PATTERN = re.compile(r"^  (/[^:]+):\s*$")

REQUIRED_RUNTIME_ENDPOINTS = {
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
}

REQUIRED_OPENAPI_TOKENS = {
    "components:",
    "securitySchemes:",
    "ApiKeyAuth:",
    "X-API-Key",
    "X-Workspace-Id",
    "FoundationRequest:",
    "FoundationResponse:",
    "ProviderStreamEvent:",
    "ProviderToolCall:",
    "AgentRunRequest:",
    "AgentSkillCall:",
    "AgentEvent:",
    "AgentEventsResponse:",
    "execute_provider:",
    "dry_run_provider:",
    "stream:",
    "stream_provider_tool_calls:",
    "stream_include_usage:",
    "stream_options:",
    "stream_chunk_chars:",
    "provider_stream_delta",
    "provider_stream_tool_call_delta",
    "provider_stream_completed",
    "tool_calls",
    "arguments_json",
    "skill_calls:",
    "enable_model_tool_loop:",
    "max_tool_rounds:",
    "allow_model_tool_provider:",
    "allow_model_tool_write:",
    "approve_model_tools:",
    "fail_on_model_tool_error:",
    "disable_events:",
}

DISALLOWED_OPENAPI_ENDPOINTS = {
    "/v1/jobs/{job_id}",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_runtime_routes(api_server_text: str, *, prefix: str = "/v1/") -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for method, path in ROUTE_PATTERN.findall(api_server_text):
        if prefix and not path.startswith(prefix):
            continue
        routes.setdefault(path, set()).add(method.upper())
    return routes


def extract_openapi_paths(openapi_text: str, *, prefix: str = "/v1/") -> set[str]:
    paths: set[str] = set()
    for line in openapi_text.splitlines():
        match = OPENAPI_PATH_PATTERN.match(line)
        if match:
            path = match.group(1)
            if not prefix or path.startswith(prefix):
                paths.add(path)
    return paths


def missing_tokens(openapi_text: str, required_tokens: set[str] | None = None) -> list[str]:
    required = required_tokens or REQUIRED_OPENAPI_TOKENS
    return sorted(token for token in required if token not in openapi_text)


def check_contract(api_server_path: Path, openapi_path: Path) -> dict[str, Any]:
    api_server_text = read_text(api_server_path)
    openapi_text = read_text(openapi_path)
    runtime_routes = extract_runtime_routes(api_server_text)
    runtime_paths = set(runtime_routes)
    openapi_paths = extract_openapi_paths(openapi_text)

    missing_required_runtime = sorted(REQUIRED_RUNTIME_ENDPOINTS - runtime_paths)
    missing_required_openapi = sorted(REQUIRED_RUNTIME_ENDPOINTS - openapi_paths)
    runtime_not_in_openapi = sorted(runtime_paths - openapi_paths)
    openapi_not_in_runtime = sorted(openapi_paths - runtime_paths)
    disallowed_declared = sorted(path for path in DISALLOWED_OPENAPI_ENDPOINTS if path in openapi_paths or path in openapi_text)
    missing_required_tokens = missing_tokens(openapi_text)

    ok = not any(
        [
            missing_required_runtime,
            missing_required_openapi,
            runtime_not_in_openapi,
            openapi_not_in_runtime,
            disallowed_declared,
            missing_required_tokens,
        ]
    )
    return {
        "ok": ok,
        "runtime_paths": sorted(runtime_paths),
        "openapi_paths": sorted(openapi_paths),
        "missing_required_runtime": missing_required_runtime,
        "missing_required_openapi": missing_required_openapi,
        "runtime_not_in_openapi": runtime_not_in_openapi,
        "openapi_not_in_runtime": openapi_not_in_runtime,
        "disallowed_declared": disallowed_declared,
        "missing_required_tokens": missing_required_tokens,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check FastAPI runtime endpoints against the static OpenAPI contract.")
    parser.add_argument("--api-server", default="inference/api_server.py")
    parser.add_argument("--openapi", default="openapi/foundation_api.openapi.yaml")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report.")
    args = parser.parse_args()

    report = check_contract(Path(args.api_server), Path(args.openapi))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "ok" if report["ok"] else "failed"
        print(f"openapi_contract_check={status}")
        for key in [
            "missing_required_runtime",
            "missing_required_openapi",
            "runtime_not_in_openapi",
            "openapi_not_in_runtime",
            "disallowed_declared",
            "missing_required_tokens",
        ]:
            if report[key]:
                print(f"{key}:")
                for item in report[key]:
                    print(f"  - {item}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
