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
- agent run contract
- provider adapter contract
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

Rate-limited responses use HTTP `429` and return:

- `Retry-After`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## Model capabilities and instances

Capabilities are abstract abilities. Model instances are deployable or external models.

Capability registry:

```text
configs/model_capability_registry.json
```

Instance registry:

```text
configs/model_instance_registry.json
```

This split is required for routing, cost control, lifecycle management and provider replacement.

## Routing modes

Router config:

```text
configs/model_router.yaml
```

Initial route modes:

- `smart`
- `cheap`
- `balanced`
- `local_first`
- `cloud_first`
- `drama_specialist`
- `code_specialist`

The router must run hard policy filters before scoring.

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

The earlier planned `/v1/jobs/{job_id}` endpoint is not in the current runtime and is intentionally not listed as implemented.

## Provider execution controls

Provider execution is explicit. `/v1/chat`, `/v1/reason`, `/v1/multimodal/analyze` and `/v1/agent/run` can route and estimate cost without calling a provider.

Execution fields:

- `execute_provider`
- `dry_run_provider`
- `base_url`
- `api_key_env`

The default is route/cost preflight only.

## Agent tool loop controls

`/v1/agent/run` supports both request-driven skill calls and model-decided tool calls.

Request-driven skill calls use `skill_calls`.

Skill permission fields:

- `allow_provider`
- `allow_write`
- `approved`
- `continue_on_error`

Request-level skill defaults:

- `allow_skill_provider`
- `allow_skill_write`
- `approve_skills`

Model-decided tool loop fields:

- `enable_model_tool_loop`
- `max_tool_rounds`
- `allow_model_tool_provider`
- `allow_model_tool_write`
- `approve_model_tools`
- `fail_on_model_tool_error`

Model-decided tool calls must use registered foundation skill ids as tool names. Tool outputs are appended as `tool_result` content blocks and passed back to the provider for the next round.

## Short drama/comic specialty

Short drama and comic capabilities are model capabilities, not the first application implementation.

The foundation exposes specialty capabilities such as:

- `drama.story_reasoning`
- `drama.visual_planning`

Applications can use these capabilities later through the same routing and API layer.

## Next implementation step

After auth audit and rate limiting v1, continue with:

1. local provider concurrency and cache controls
2. provider usage reconciliation
3. streaming run events
4. workspace-level budget and quota checks
5. distributed rate limiting backend
