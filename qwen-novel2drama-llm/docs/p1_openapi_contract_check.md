# P1 OpenAPI Contract Check

This tool keeps the FastAPI runtime and static OpenAPI contract aligned.

Implemented files:

- `scripts/check_openapi_contract.py`
- `tests/test_openapi_contract_check.py`
- `.github/workflows/foundation-contract-check.yml`
- `.github/workflows/foundation-optional-profiles.yml`
- `scripts/ci_profiles.py`

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

Inspect CI profiles:

```bash
python scripts/ci_profiles.py --profile all --json
```

Expected success output:

```text
openapi_contract_check=ok
```

## CI

Default workflow:

```text
.github/workflows/foundation-contract-check.yml
```

The default workflow runs on:

- `push` to `main`
- `pull_request`
- `workflow_dispatch`

It is path-filtered to changes under:

- `qwen-novel2drama-llm/**`
- `.github/workflows/foundation-contract-check.yml`

Default jobs:

- `openapi-contract`: runs `contracts` profile.
- `lightweight-core-tests`: runs `core` profile.

Optional workflow:

```text
.github/workflows/foundation-optional-profiles.yml
```

Optional profile selections:

- `optional`
- `provider-adapter`
- `api-server`
- `local-provider-contract`
- `heavyweight`
- `local-model-imports`
- `all`

Current default CI commands:

```bash
python scripts/check_openapi_contract.py
python -m unittest tests.test_openapi_contract_check tests.test_foundation_contracts
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_ci_profiles tests.test_workspace_quota tests.test_skill_registry tests.test_mcp_adapter
```

## Purpose

The foundation API now includes router, token/cost, memory, rules, skills, MCP, API key mode, provider execution, provider streaming, streamed tool-call reconstruction, Agent stream tool bridge, incremental stream tool execution, same-stream continuation fallback events, workspace quota controls, Agent tool loop controls and live Agent event reads.

This check helps keep runtime routes and the static OpenAPI file consistent as the API changes while keeping heavyweight provider/model dependency checks in separate opt-in profiles.

## Current limitations

- The script uses lightweight static parsing.
- It checks paths and important tokens, not full OpenAPI semantic validity.
- It only compares `/v1/*` runtime endpoints.
- Heavy local model profile checks dependency imports only; it does not download or load real model weights.
- Real provider smoke tests with credentials are not implemented yet.

## Next steps

- Add full OpenAPI schema validation later.
- Add generated client smoke tests.
- Add endpoint-level scope consistency checks later.
- Add provider-specific credential-gated smoke profiles later.
