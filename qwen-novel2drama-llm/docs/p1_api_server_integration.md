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

To call a provider adapter:

```json
{
  "execute_provider": true,
  "base_url": "https://provider.example/v1",
  "api_key_env": "MODEL_API_KEY"
}
```

To stream provider output as SSE:

```json
{
  "route_mode": "cloud_first",
  "execute_provider": true,
  "stream": true,
  "base_url": "https://provider.example/v1",
  "api_key_env": "MODEL_API_KEY",
  "input": [{"type": "text", "text": "hello"}]
}
```

For OpenAI-compatible providers, the adapter sends native `stream=true` to `/chat/completions`, parses provider SSE `data: {...}` lines, stops on `data: [DONE]`, and converts deltas into foundation `ProviderStreamEvent` chunks.

To ask compatible providers for final stream usage when they support it:

```json
{
  "stream": true,
  "stream_include_usage": true
}
```

SSE provider frames use:

```text
id: <chunk_id>
event: provider_stream_delta
data: <provider stream event JSON>
```

Provider stream event types:

- `provider_stream_started`
- `provider_stream_delta`
- `provider_stream_completed`
- `provider_stream_failed`

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

Local provider stream dry-run:

```json
{
  "route_mode": "local_first",
  "execute_provider": true,
  "stream": true,
  "dry_run_provider": true,
  "stream_chunk_chars": 32,
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
  "stream": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Local provider cache and concurrency controls:

- `use_cache`: reuse loaded model runtime in the current process.
- `disable_cache`: request-level opt-out.
- `serialize_generation`: serialize generation per cached model runtime.
- `stream_chunk_chars`: chunk size for fallback chunked streaming.
- `force_chunked_stream`: force full-generation chunk fallback even when native streaming exists.
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

## Current limitations

- Agent SSE currently polls the JSONL event file.
- `/v1/chat` provider streaming is SSE only, not WebSocket.
- OpenAI-compatible streaming currently handles text deltas; streamed tool-call delta reconstruction is not implemented yet.
- Model-decided tool loop is synchronous.
- Tool names must map to registered foundation skill ids.
- Local provider is text-only and loads weights in-process.
- Local provider cache is process-local.
- Auth is API-key based, not full OAuth/OIDC.
- Rate limit state is file based, not distributed.
- No database-backed memory or run store yet.

## Next steps

- Add streamed tool-call delta reconstruction.
- Add workspace-level budget and quota checks.
- Add distributed rate limiting backend.
- Add resume/cancel/retry for Agent runs.
