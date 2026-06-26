# Foundation API Contract v0.1

This document defines the first machine-readable contract layer for the AI foundation platform.

The goal is to move from research draft to engineering contract. This is not yet the full service implementation.

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

Every API should return a standard envelope with:

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

Initial endpoints:

- `POST /v1/chat`
- `POST /v1/reason`
- `POST /v1/multimodal/analyze`
- `POST /v1/token/count`
- `POST /v1/cost/estimate`
- `POST /v1/memory/search`
- `POST /v1/memory/write`
- `POST /v1/rules/evaluate`
- `GET /v1/skills/list`
- `POST /v1/skills/call`
- `GET /v1/mcp/tools`
- `POST /v1/agent/run`
- `GET /v1/jobs/{job_id}`

## Short drama/comic specialty

Short drama and comic capabilities are model capabilities, not the first application implementation.

The foundation exposes specialty capabilities such as:

- `drama.story_reasoning`
- `drama.visual_planning`

Applications can use these capabilities later through the same routing and API layer.

## Next implementation step

After this contract layer, implement:

1. schema validators
2. registry inspectors
3. model router service
4. token/cost services
5. memory and rule services
6. provider adapter interface
7. API route skeleton
