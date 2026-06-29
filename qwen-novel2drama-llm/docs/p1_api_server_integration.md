# P1 API Server Integration

The FastAPI server exposes foundation services through `/v1/*` routes while preserving the legacy `/generate` local model endpoint.

## Foundation endpoints

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
- `GET /v1/agent/runs`
- `GET /v1/agent/events`
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

## Start server

Local model mode:

```bash
python inference/api_server.py --model-path /path/to/model
```

Foundation-only mode:

```bash
python inference/api_server.py --skip-model-load
```

## Auth, audit and rate limits

Auth is disabled by default for local development. Enable API key enforcement with:

```bash
FOUNDATION_AUTH_REQUIRED=true FOUNDATION_API_KEYS=configs/auth/api_keys.json python inference/api_server.py --skip-model-load
```

Headers:

```text
X-API-Key: your_api_key
X-Workspace-Id: your_workspace_id
```

`/health`, `/v1/health`, `/docs` and `/openapi.json` remain public.

## Chat and provider execution

`/v1/chat`, `/v1/reason` and `/v1/multimodal/analyze` route the request first. By default, provider execution is skipped and the API returns route, usage and cost estimates.

To stream provider output as SSE, pass `execute_provider=true` and `stream=true`. OpenAI-compatible providers send native `stream=true` to `/chat/completions`, parse provider SSE, and convert text/tool-call deltas into foundation `ProviderStreamEvent` chunks.

## Agent runtime and events

`/v1/agent/run` supports provider execution, request-defined skill calls, model-decided tool calls, stream tool-call bridging, incremental stream tool execution, workspace quota and run events.

Agent events are always written to compatibility JSONL when events are enabled:

```text
outputs/agent_runtime/api/<run_id>/events.jsonl
```

Selected run store event reads:

```text
GET /v1/agent/events?run_id=demo-run
GET /v1/agent/events?run_id=demo-run&stream=true
```

File mode reads JSONL. SQLite mode reads `run_events`. Postgres mode reads `run_events` through `PostgresRunStore` when the optional dependency and DSN are configured.

## Agent lifecycle APIs and run store

Lifecycle functions use the `agent/run_store.py` boundary:

```text
RunStore
FileRunStore
SQLiteRunStore
PostgresRunStore
build_run_store(kind, output_root, sqlite_path=None, postgres_dsn=None)
```

Supported values:

```text
FOUNDATION_AGENT_RUN_STORE=file|sqlite|postgres
```

SQLite config:

```bash
FOUNDATION_AGENT_RUN_STORE=sqlite FOUNDATION_AGENT_RUN_DB=outputs/agent_runtime/runs.sqlite python inference/api_server.py --skip-model-load
```

Postgres config:

```text
FOUNDATION_AGENT_RUN_STORE=postgres
FOUNDATION_AGENT_RUN_POSTGRES_DSN=<configured outside git>
```

Postgres dependency profile:

```bash
python -m pip install -r requirements/postgres-run-store.txt
```

Postgres schema and migration runner:

```text
migrations/postgres_run_store.sql
scripts/apply_postgres_run_store_migration.py
```

Dry-run migration plan:

```bash
python scripts/apply_postgres_run_store_migration.py --dry-run --json
```

Apply migration:

```bash
python scripts/apply_postgres_run_store_migration.py --json
```

Optional pool env:

```text
FOUNDATION_AGENT_RUN_POSTGRES_POOL_ENABLED=false
FOUNDATION_AGENT_RUN_POSTGRES_POOL_MIN=1
FOUNDATION_AGENT_RUN_POSTGRES_POOL_MAX=5
FOUNDATION_AGENT_RUN_POSTGRES_POOL_TIMEOUT=30
```

Example env template:

```text
configs/run_store/postgres.example.env
```

When `/v1/agent/run` completes, runtime writes request/report/artifact index into the selected run store while retaining file artifacts for compatibility.

Run listing:

```text
GET /v1/agent/runs?status=completed&workspace_id=w1&query=demo&limit=50&offset=0&order=desc
```

Supported list filters:

- `status`
- `owner_id`
- `project_id`
- `workspace_id`
- `parent_run_id`
- `query`
- `limit`
- `offset`
- `order=asc|desc`

Lifecycle endpoints:

```text
GET /v1/agent/status?run_id=demo-run
POST /v1/agent/cancel
POST /v1/agent/retry
POST /v1/agent/resume
```

All lifecycle, event and run listing endpoints use `agent:run` auth scope.

## Current limitations

- Runtime still writes compatibility file artifacts.
- SQLite events are local-node events, not a distributed event bus.
- Postgres migration runner and pool config exist, but schema version tracking, health checks and production deployment profiles are not complete.
- Real Postgres tests are DSN-gated and not part of default core CI.
- Worker leases are cooperative and not a full worker queue.
- SSE is polling-based, not WebSocket or push-based infrastructure.
- Cancel is cooperative and does not forcibly terminate an in-flight provider call.
- Retry/resume are replay-based child runs, not arbitrary stack-frame continuation.
- Auth is API-key based, not OAuth/OIDC.
