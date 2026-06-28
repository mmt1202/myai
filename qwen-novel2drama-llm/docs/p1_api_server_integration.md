# P1 API Server Integration

The FastAPI server exposes foundation services through `/v1/*` routes while preserving the old `/generate` local model endpoint.

Implemented files:

- `inference/api_server.py`
- `agent/run_store.py`
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

The second mode is useful for routing, token/cost, memory, rules, skills, MCP, Agent runtime, Agent lifecycle and provider API testing.

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
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

The legacy `POST /generate` endpoint remains and still requires a loaded local model.

## Chat and provider execution

`/v1/chat`, `/v1/reason` and `/v1/multimodal/analyze` route the request first.

By default, provider execution is skipped and the API returns route, usage and cost estimates.

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

For OpenAI-compatible providers, the adapter sends native `stream=true` to `/chat/completions`, parses provider SSE `data: {...}` lines, stops on `data: [DONE]`, and converts text/tool-call deltas into foundation `ProviderStreamEvent` chunks.

## Agent provider execution, tool loops and live events

`/v1/agent/run` supports provider execution, request-defined skill calls, model-decided tool calls, stream tool-call bridging, incremental stream tool execution, workspace quota and run events through `agent/runtime.py`.

Provider preflight only:

```json
{
  "run_id": "demo-run",
  "task": "summarize this",
  "route_mode": "smart",
  "approval_policy": "never"
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

## Agent lifecycle APIs and run store

The API server exposes lifecycle controls from `agent/lifecycle.py`.

Lifecycle functions now use the `agent/run_store.py` boundary:

```text
RunStore
FileRunStore
file_run_store(output_root)
```

The API server defaults to `FileRunStore` under:

```text
outputs/agent_runtime/api/<run_id>/
```

It can also select local SQLite-backed run state with:

```text
MYAI_AGENT_RUN_STORE=sqlite
MYAI_AGENT_SQLITE_RUN_STORE_PATH=outputs/agent_runtime/api/runs.sqlite3
```

For lifecycle calls, request bodies may set `run_store: "sqlite"` and `sqlite_path`; status may pass `run_store` and `sqlite_path` as query parameters.

Status:

```text
GET /v1/agent/status?run_id=demo-run
```

Cancel:

```json
POST /v1/agent/cancel
{
  "run_id": "demo-run",
  "reason": "user_requested",
  "requested_by": "operator"
}
```

Retry:

```json
POST /v1/agent/retry
{
  "run_id": "demo-run",
  "new_run_id": "demo-run-retry",
  "overrides": {
    "task": "retry with revised prompt"
  }
}
```

Resume:

```json
POST /v1/agent/resume
{
  "run_id": "demo-run",
  "new_run_id": "demo-run-resume",
  "overrides": {
    "skill_calls": []
  },
  "allow_completed": false
}
```

All lifecycle endpoints use `agent:run` auth scope.

Run-store selection is intentionally local-only in this phase: `file` remains the default, and `sqlite` uses the standard-library `SQLiteRunStore`. This does not provide distributed worker leasing or Postgres semantics.

Current lifecycle behavior:

- `status` reads through the selected run store.
- `cancel` writes a cancel marker through the selected run store and updates non-terminal reports to `cancelled`.
- `retry` loads the saved request from the selected run store, merges overrides, creates a child run with `retry_of`, and persists the child request/report back into SQLite when SQLite is selected.
- `resume` loads the saved request from the selected run store, merges overrides, creates a child run with `resume_of`, and persists the child request/report back into SQLite when SQLite is selected.

## Current limitations

- Agent SSE currently polls the JSONL event file.
- `FileRunStore` and local `SQLiteRunStore` are implemented run stores.
- Runtime writes still use file paths directly; lifecycle reads/writes use the store boundary.
- No Postgres run store yet; SQLite is local-only.
- No transaction, lock, lease or distributed concurrency control yet.
- Cancel is cooperative and does not forcibly terminate an in-flight provider call.
- Retry/resume are replay-based child runs, not arbitrary stack-frame continuation.
- `/v1/chat` provider streaming is SSE only, not WebSocket.
- Same-stream tool result injection is still provider capability gated; built-in providers currently fall back.
- Model-decided tool loop is synchronous.
- Local provider is text-only and loads weights in-process.
- Auth is API-key based, not full OAuth/OIDC.
- Rate limit and workspace quota state are file based, not distributed.

## Next steps

- Add Postgres run store implementation and distributed lease semantics.
- Migrate runtime artifact writes to the run store interface.
- Add distributed quota/rate limit backend.
- Add provider-native bidirectional continuation adapter.
- Add secret-gated real provider smoke tests.
