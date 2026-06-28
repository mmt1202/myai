# Foundation API Contract v0.1

This document defines the first machine-readable contract layer for the AI foundation platform.

The project has moved from research draft to engineering contracts and early runtime service implementations. The OpenAPI contract must stay aligned with the FastAPI runtime in `inference/api_server.py`.

## Contract files

- `configs/schemas/content_block_schema.json`
- `configs/schemas/error_code_schema.json`
- `configs/schemas/response_envelope_schema.json`
- `configs/model_capability_registry.json`
- `configs/model_instance_registry.json`
- `configs/model_router.yaml`
- `openapi/foundation_api.openapi.yaml`

## Core principle

Applications are not built inside the foundation layer. Applications use the foundation through stable APIs.

The foundation layer owns:

- model capability registry
- model instance registry
- routing policy
- multimodal content block protocol
- token and cost accounting contract
- memory contract
- rules contract
- skills and MCP contract
- agent run, lifecycle and event stream contract
- provider adapter and provider stream contract
- API key and workspace scope contract
- auth audit and rate limit contract
- response envelope and error code contract

## Unified content blocks

All chat, reasoning, multimodal, memory, skill and agent APIs should accept content blocks.

Supported block types:

- `text`
- `image`
- `video`
- `audio`
- `subtitle`
- `metadata`
- `file`
- `url`
- `tool_result`
- `reasoning_hint`

Schema:

```text
configs/schemas/content_block_schema.json
```

## Response envelope

Every foundation API should return a standard envelope with:

- `request_id`
- `trace_id`
- `status`
- `model`
- `usage`
- `cost`
- `output`
- `warnings`
- `error`
- `route`

Schema:

```text
configs/schemas/response_envelope_schema.json
```

## Auth contract

OpenAPI declares `ApiKeyAuth` using:

```text
X-API-Key
```

Workspace binding uses:

```text
X-Workspace-Id
```

Auth is disabled by default for local development and can be enabled with:

```text
FOUNDATION_AUTH_REQUIRED=true
FOUNDATION_API_KEYS=configs/auth/api_keys.json
```

Public endpoints:

- `/health`
- `/v1/health`
- `/docs`
- `/openapi.json`

Agent lifecycle endpoints use `agent:run` scope.

Auth audit events are written to:

```text
outputs/auth/auth_audit.jsonl
```

Rate limiting can be enabled with:

```text
FOUNDATION_RATE_LIMIT_ENABLED=true
FOUNDATION_RATE_LIMITS=configs/auth/rate_limits.json
FOUNDATION_RATE_LIMIT_STATE=outputs/auth/rate_limit_state.json
```

## OpenAPI surface

OpenAPI file:

```text
openapi/foundation_api.openapi.yaml
```

Runtime-aligned endpoints:

- `GET /v1/health`
- `POST /v1/chat`
- `POST /v1/reason`
- `POST /v1/multimodal/analyze`
- `POST /v1/route`
- `POST /v1/token/count`
- `POST /v1/cost/estimate`
- `POST /v1/memory/search`
- `POST /v1/memory/write`
- `POST /v1/rules/evaluate`
- `GET /v1/skills/list`
- `POST /v1/skills/call`
- `GET /v1/mcp/tools`
- `POST /v1/mcp/call`
- `POST /v1/agent/run`
- `GET /v1/agent/events`
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

The earlier planned `/v1/jobs/{job_id}` endpoint is not in the current runtime and is intentionally not listed as implemented.

## Agent lifecycle contract

Agent lifecycle endpoints wrap `agent/lifecycle.py` file-backed controls:

- `GET /v1/agent/status?run_id=...`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

Lifecycle request schema:

```text
AgentLifecycleRequest
```

Lifecycle response output schema:

```text
AgentLifecycleResponse
```

Current behavior:

- `status` reads `agent_run_report.json` and `events.jsonl`.
- `cancel` writes `cancel_requested.json`.
- `retry` replays `agent_request.json` as a child run with `retry_of`.
- `resume` replays `agent_request.json` as a child run with `resume_of`.

This is not a database run store or distributed queue.

## Provider execution and stream controls

Provider execution is explicit. `/v1/chat`, `/v1/reason`, `/v1/multimodal/analyze` and `/v1/agent/run` can route and estimate cost without calling a provider.

Execution fields:

- `execute_provider`
- `dry_run_provider`
- `base_url`
- `api_key_env`

Stream fields:

- `stream`
- `stream_chunk_chars`
- `force_chunked_stream`
- `stream_include_usage`
- `stream_options`
- `stream_provider_tool_calls`
- `incremental_stream_tool_execution`
- `same_stream_tool_result_injection`

`/v1/chat` returns `text/event-stream` when `stream=true` and `execute_provider=true`.

OpenAI-compatible provider streaming sends `stream=true` to `/chat/completions`, parses provider SSE `data: {...}` lines, stops on `data: [DONE]`, and converts text/tool-call deltas into `ProviderStreamEvent` chunks.
