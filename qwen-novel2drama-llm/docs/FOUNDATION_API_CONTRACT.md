# Foundation API Contract

This document freezes the repository-level Foundation API contract.

## Common response envelope

Most `/v1/*` APIs return:

```json
{
  "status": "ok",
  "request_id": "optional request id",
  "trace_id": "optional trace id",
  "output": {},
  "usage": {},
  "cost": {},
  "route": {},
  "warnings": [],
  "error": null
}
```

Failed responses use:

```json
{
  "status": "failed",
  "output": null,
  "error": {
    "code": "string",
    "message": "string",
    "retryable": false,
    "details": {}
  }
}
```

## Headers

- `X-API-Key`: API key when auth is enabled.
- `X-Workspace-Id`: workspace scope for auth/quota/audit.
- `X-Request-Id`: optional caller request id.

## Health and readiness

### `GET /health`

Basic process health.

### `GET /v1/health`

Foundation capability health summary.

### `GET /v1/ready`

Readiness report with component status.

### `GET /v1/health/deep`

Deep readiness report with run store, quota backend, memory backend, provider registry and queue summary.

## Routing and usage

### `POST /v1/token/count`

Body: content block request.

Output: estimated usage.

### `POST /v1/cost/estimate`

Body: request plus optional `model_id`.

Output: estimated usage and cost.

### `POST /v1/route`

Body:

```json
{
  "route_mode": "balanced",
  "required_capabilities": ["text.chat"],
  "input": [{"type": "text", "text": "hello"}]
}
```

Output: selected model, candidates, rejected candidates, fallback chain and estimated usage.

## Memory

Memory backend selection:

```text
FOUNDATION_MEMORY_BACKEND=file|sqlite|vector
FOUNDATION_MEMORY_STORE=outputs/memory/memory.jsonl
FOUNDATION_MEMORY_DB=outputs/memory/memory.sqlite
```

### `POST /v1/memory/write`

Writes a scoped memory item. Output includes the stored item and `memory_store` metadata.

### `POST /v1/memory/search`

Searches scoped memory and returns memory items. Output includes `items` and `memory_store` metadata.

Stable item fields:

```json
{
  "id": "...",
  "scope": "project",
  "owner_id": null,
  "project_id": "...",
  "content": "...",
  "tags": [],
  "sensitivity": "internal",
  "importance": 0.5,
  "score": 1.0,
  "metadata": {}
}
```

Vector backend may add `lexical_score` and `vector_score`.

## Skills

### `GET /v1/skills/list`

Query parameters: `category`, `status`, `capability`, `include_planned`.

### `POST /v1/skills/call`

Body:

```json
{
  "name": "drama.novel_to_outline",
  "arguments": {"text": "...", "episode_count": 3},
  "allow_provider": false,
  "allow_write": false,
  "approved": false
}
```

## MCP-style adapter

### `GET /v1/mcp/tools`

Lists Foundation tools as MCP-compatible tool descriptors.

### `POST /v1/mcp/call`

Calls a registered MCP-style tool.

## Agent runtime

### `POST /v1/agent/run`

Runs the lightweight Foundation Agent.

### `GET /v1/agent/runs`

Lists runs with filters.

### `GET /v1/agent/events`

Returns events for a run. `stream=true` returns Server-Sent Events.

SSE event shape:

```text
id: <event_id>
event: <event_type>
data: <json event>
```

### `GET /v1/agent/status`

Returns run status.

### `POST /v1/agent/cancel`

Creates a cancel request for a run.

### `POST /v1/agent/retry`

Retries a prior run.

### `POST /v1/agent/resume`

Resumes a waiting or completed run when allowed.

## Provider text APIs

### `POST /v1/chat`

Routes and optionally executes a chat generation request.

### `POST /v1/reason`

Reasoning-oriented wrapper over chat.

### `POST /v1/multimodal/analyze`

Multimodal analysis route contract.

## Drama APIs

Drama pure handlers live in `drama/api.py` and FastAPI route contract lives in `drama/fastapi_router.py`:

- `/v1/drama/parse`
- `/v1/drama/outline`
- `/v1/drama/characters`
- `/v1/drama/storyboard`
- `/v1/drama/prompts`
- `/v1/drama/quality`
- `/v1/drama/pipeline`

Direct media generation handlers live in `drama/generation_api.py`.

## ID rules

- `request_id`: caller-supplied request id.
- `trace_id`: distributed trace id; defaults to request id if omitted.
- `run_id`: run-store safe id. It must not contain path separators or `..`.

## Compatibility rule

New fields may be added, but existing field names and response envelope shape should remain backward compatible for ForgePilot.
