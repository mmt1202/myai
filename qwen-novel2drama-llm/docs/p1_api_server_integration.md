# P1 API Server Integration

The FastAPI server now exposes foundation services through `/v1/*` routes while preserving the old `/generate` local model endpoint.

Implemented files:

- `inference/api_server.py`
- `tests/test_api_server_foundation.py`

## Start server

Start with local model loading:

```bash
python inference/api_server.py --model-path /path/to/model
```

Start only foundation APIs without loading local model weights:

```bash
python inference/api_server.py --skip-model-load
```

The second mode is useful for routing, token/cost, memory, rules, skills, MCP and agent API testing.

## Auth, audit and rate limit mode

Auth is disabled by default for local development.

Enable API key enforcement:

```bash
FOUNDATION_AUTH_REQUIRED=true \
FOUNDATION_API_KEYS=configs/auth/api_keys.json \
python inference/api_server.py --skip-model-load
```

Use headers:

```text
X-API-Key: your_api_key
X-Workspace-Id: your_workspace_id
```

`/health`, `/v1/health`, `/docs` and `/openapi.json` remain public.

Auth audit events are written to:

```text
outputs/auth/auth_audit.jsonl
```

Enable rate limiting:

```bash
FOUNDATION_RATE_LIMIT_ENABLED=true \
FOUNDATION_RATE_LIMITS=configs/auth/rate_limits.json \
FOUNDATION_RATE_LIMIT_STATE=outputs/auth/rate_limit_state.json \
python inference/api_server.py --skip-model-load
```

Rate-limited responses return HTTP `429` with:

```text
Retry-After
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```

## Foundation endpoints

Runtime endpoints:

- `GET /v1/health`
- `POST /v1/chat`
- `POST /v1/reason`
- `POST /v1/multimodal/analyze`
- `POST /v1/token/count`
- `POST /v1/cost/estimate`
- `POST /v1/route`
- `POST /v1/memory/search`
- `POST /v1/memory/write`
- `POST /v1/rules/evaluate`
- `GET /v1/skills/list`
- `POST /v1/skills/call`
- `GET /v1/mcp/tools`
- `POST /v1/mcp/call`
- `POST /v1/agent/run`
- `GET /v1/agent/events`

The legacy `POST /generate` endpoint remains and still requires a loaded local model.

## Chat and provider execution

`/v1/chat`, `/v1/reason` and `/v1/multimodal/analyze` route the request first.

By default, provider execution is skipped and the API returns route, usage and cost estimates.

To call a provider adapter, pass:

```json
{
  "execute_provider": true,
  "base_url": "https://provider.example/v1",
  "api_key_env": "MODEL_API_KEY"
}
```

## Local provider execution

The local model instance `local.qwen2_5_1_5b_instruct` uses `providers/local_text.py` through the provider factory.

Local provider dry-run does not load model weights:

```json
{
  "route_mode": "local_first",
  "execute_provider": true,
  "dry_run_provider": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Real local execution needs a model path:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python inference/api_server.py --skip-model-load
```

or a request field:

```json
{
  "execute_provider": true,
  "model_path": "/path/to/model",
  "use_cache": true,
  "serialize_generation": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Local provider cache and concurrency controls:

- `use_cache`: reuse loaded model runtime in the current process.
- `disable_cache`: request-level opt-out.
- `serialize_generation`: serialize generation per cached model runtime.
- `providers.local_text.cache_stats()`: inspect process-local cache state.
- `providers.local_text.clear_model_cache()`: clear process-local cache state.

## Agent provider execution, tool loops and live events

`/v1/agent/run` supports provider execution, request-defined skill calls, model-decided tool calls and run events through `agent/runtime.py`.

Provider preflight only:

```json
{
  "run_id": "demo-run",
  "task": "summarize this",
  "route_mode": "smart",
  "approval_policy": "never"
}
```

Provider dry-run execution:

```json
{
  "run_id": "demo-run",
  "task": "summarize this",
  "route_mode": "smart",
  "approval_policy": "never",
  "execute_provider": true,
  "dry_run_provider": true,
  "base_url": "http://localhost:8000/v1"
}
```

Request-driven skill loop execution:

```json
{
  "task": "count tokens before running",
  "route_mode": "balanced",
  "approval_policy": "never",
  "skill_calls": [
    {
      "name": "foundation.token_count",
      "arguments": {
        "request": {"input": [{"type": "text", "text": "hello"}]},
        "expected_output_tokens": 10
      }
    }
  ]
}
```

Model-decided tool loop execution:

```json
{
  "task": "use tools if needed",
  "route_mode": "smart",
  "approval_policy": "never",
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "max_tool_rounds": 3,
  "allow_model_tool_write": false,
  "approve_model_tools": false
}
```

Model-decided tool calls must use registered foundation skill ids as tool names. Tool results are appended as `tool_result` content blocks and sent back to the provider in the next round.

Agent events are written to:

```text
outputs/agent_runtime/api/<request_id-or-run_id-or-latest>/events.jsonl
```

Read events as JSON:

```text
GET /v1/agent/events?run_id=demo-run
```

Stream events as SSE:

```text
GET /v1/agent/events?run_id=demo-run&stream=true
```

Supported event query parameters:

- `run_id`
- `stream`
- `since_event_id`
- `limit`
- `poll_interval`
- `max_seconds`

SSE response frames use:

```text
id: <event_id>
event: <event_type>
data: <full event JSON>
```

Disable event writing per request:

```json
{
  "disable_events": true
}
```

The agent writes run artifacts under:

```text
outputs/agent_runtime/api/<request_id-or-run_id-or-latest>/
```

Artifacts can include:

- `agent_run_report.json`
- `events.jsonl`
- `provider_response.json`
- `skill_results.json`
- `model_tool_loop.json`
- `usage_ledger.jsonl`

## Memory

The API uses:

```text
outputs/memory/memory.jsonl
```

for the default JSONL memory store.

## MCP

`/v1/mcp/tools` exposes skills as MCP-style tools.

`/v1/mcp/call` calls the MCP adapter with optional permission flags:

- `allow_provider`
- `allow_write`
- `approved`

## Current limitations

- Agent SSE currently polls the JSONL event file.
- Model-decided tool loop is synchronous.
- Tool names must map to registered foundation skill ids.
- Local provider is text-only and loads weights in-process.
- Local provider cache is process-local.
- Auth is API-key based, not full OAuth/OIDC.
- Rate limit state is file based, not distributed.
- No database-backed memory or run store yet.
- WebSocket events are not implemented yet.

## Next steps

- Add local provider streaming support.
- Add workspace-level budget and quota checks.
- Add distributed rate limiting backend.
- Add resume/cancel/retry for Agent runs.
