# P1 OpenAPI Contract Check

This tool keeps the FastAPI runtime and static OpenAPI contract aligned.

Implemented files:

- `scripts/check_openapi_contract.py`
- `tests/test_openapi_contract_check.py`
- `.github/workflows/foundation-contract-check.yml`

## Checks

The checker compares:

- `/v1/*` routes declared in `inference/api_server.py`
- `/v1/*` paths declared in `openapi/foundation_api.openapi.yaml`

It also checks that important OpenAPI sections and fields are present, including:

- `ApiKeyAuth`
- `FoundationRequest`
- `FoundationResponse`
- `ProviderStreamEvent`
- `ProviderToolCall`
- `AgentRunRequest`
- `AgentSkillCall`
- `AgentEvent`
- `AgentEventsResponse`
- provider execution fields
- provider streaming fields such as `stream`, `stream_provider_tool_calls`, `incremental_stream_tool_execution`, `same_stream_tool_result_injection`, `stream_include_usage`, `stream_options`, `stream_chunk_chars` and provider stream events
- continuation stream events such as `provider_stream_tool_result`, `provider_stream_continuation_unsupported` and `provider_stream_continuation_failed`
- workspace quota fields such as `workspace_quota_enabled`, `workspace_quota_config_path` and `workspace_quota_state_path`
- streamed tool-call reconstruction fields such as `provider_stream_tool_call_delta`, `tool_calls` and `arguments_json`
- request-driven skill loop fields
- model tool loop fields
- Agent event stream fields such as `disable_events` and `text/event-stream`

Current required runtime endpoints include `GET /v1/agent/events`.

## Run locally

From project root:

```bash
python scripts/check_openapi_contract.py
```

JSON report:

```bash
python scripts/check_openapi_contract.py --json
```

Expected success output:

```text
openapi_contract_check=ok
```

## CI

GitHub Actions workflow:

```text
.github/workflows/foundation-contract-check.yml
```

The workflow runs on:

- `push` to `main`
- `pull_request`
- `workflow_dispatch`

It is path-filtered to changes under:

- `qwen-novel2drama-llm/**`
- `.github/workflows/foundation-contract-check.yml`

Jobs:

- `openapi-contract`: runs `python scripts/check_openapi_contract.py` and contract unit tests.
- `lightweight-core-tests`: runs dependency-free service tests that do not require torch, transformers, peft or provider SDKs.

Current CI commands:

```bash
python scripts/check_openapi_contract.py
python -m unittest tests.test_openapi_contract_check tests.test_foundation_contracts
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_workspace_quota tests.test_skill_registry tests.test_mcp_adapter
```

## Purpose

The foundation API now includes router, token/cost, memory, rules, skills, MCP, API key mode, provider execution, provider streaming, streamed tool-call reconstruction, Agent stream tool bridge, incremental stream tool execution, same-stream continuation fallback events, workspace quota controls, Agent tool loop controls and live Agent event reads.

This check helps keep runtime routes and the static OpenAPI file consistent as the API changes.

## Current limitations

- The script uses lightweight static parsing.
- It checks paths and important tokens, not full OpenAPI semantic validity.
- It only compares `/v1/*` runtime endpoints.
- The CI workflow intentionally avoids heavyweight model/provider tests until dependency setup is defined.

## Next steps

- Add full OpenAPI schema validation later.
- Add generated client smoke tests.
- Add endpoint-level scope consistency checks later.
- Add heavyweight provider/model CI once dependency profiles are defined.
