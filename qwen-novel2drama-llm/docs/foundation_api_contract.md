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

## Agent skill loop controls

`/v1/agent/run` supports request-driven skill calls through `skill_calls`.

Skill permission fields:

- `allow_provider`
- `allow_write`
- `approved`
- `continue_on_error`

Request-level defaults:

- `allow_skill_provider`
- `allow_skill_write`
- `approve_skills`

This is not yet model-decided multi-turn tool calling.

## Short drama/comic specialty

Short drama and comic capabilities are model capabilities, not the first application implementation.

The foundation exposes specialty capabilities such as:

- `drama.story_reasoning`
- `drama.visual_planning`

Applications can use these capabilities later through the same routing and API layer.

## Next implementation step

After auth/API key/workspace scope, continue with:

1. local provider adapter for the existing local model runtime
2. model-decided multi-turn tool loop
3. OpenAPI lint/check tooling
4. provider usage reconciliation
5. auth audit log and rate limiting
