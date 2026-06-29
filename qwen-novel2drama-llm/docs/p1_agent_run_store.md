# P1 Agent Run Store

This layer introduces a replaceable run store contract for Agent run state, event reads, run listing, lifecycle state and worker leases.

Implemented files:

- `agent/run_store.py`
- `agent/sqlite_run_store.py`
- `agent/postgres_run_store.py`
- `agent/events.py`
- `agent/runtime.py`
- `agent/lifecycle.py`
- `inference/api_server.py`
- `tests/test_run_store.py`
- `tests/test_sqlite_run_store.py`
- `tests/test_agent_events.py`
- `tests/test_agent_lifecycle.py`
- `tests/test_api_server_foundation.py`

## Purpose

Before this layer, Agent lifecycle code read and wrote these files directly:

- `agent_request.json`
- `agent_run_report.json`
- `events.jsonl`
- `cancel_requested.json`

The run store abstraction makes those operations explicit so future database-backed stores can replace the file-backed implementation without rewriting lifecycle APIs.

## Contract

Implemented stores:

```text
FileRunStore
SQLiteRunStore
PostgresRunStore scaffold
```

Factories:

```python
file_run_store(output_root)
sqlite_run_store(db_path)
postgres_run_store(dsn=None, output_root=None, connect=False)
build_run_store(kind, output_root, sqlite_path=None, postgres_dsn=None)
```

Supported run store kinds:

```text
file
sqlite
sqlite3
postgres
postgresql
pg
```

`build_run_store()` defaults to file-backed storage. For SQLite, the default database path is:

```text
<output_root>/runs.sqlite
```

For Postgres scaffold, the DSN is read from:

```text
FOUNDATION_AGENT_RUN_POSTGRES_DSN
```

Core operations:

- `safe_run_id(run_id)`
- `run_dir(run_id)`
- `artifact_path(run_id, name)`
- `load_request(run_id)`
- `save_request(run_id, request)`
- `load_report(run_id)`
- `save_report(run_id, report)`
- `load_events(run_id)`
- `event_summary(run_id)`
- `load_cancel_request(run_id)`
- `save_cancel_request(run_id, marker)`
- `cancel_requested(run_id)`
- `save_artifact(run_id, name, artifact, path=None)`
- `list_runs(...)`
- `claim_run(run_id, worker_id, lease_seconds=60)`
- `renew_lease(run_id, worker_id, lease_seconds=60)`
- `release_run(run_id, worker_id)`
- `find_expired_leases()`
- `status(run_id)`
- `metadata()`

SQLite also implements `append_event(run_id, event)`. Runtime uses this for live DB-backed event indexing while preserving JSONL event files.

## Run listing/query

Both file and SQLite stores expose:

```python
list_runs(
    status=None,
    owner_id=None,
    project_id=None,
    workspace_id=None,
    parent_run_id=None,
    query=None,
    limit=50,
    offset=0,
    order="desc",
)
```

`query` is a lightweight substring search over run id, task, status, error, owner/project/workspace id and selected model id. This is not a full-text search engine.

## Worker leases

Worker lease v1 is a cooperative claim layer for future distributed Agent workers.

Operations:

```python
claim_run(run_id, worker_id, lease_seconds=60)
renew_lease(run_id, worker_id, lease_seconds=60)
release_run(run_id, worker_id)
find_expired_leases()
```

Rules:

- one active lease per run
- same worker can renew an active lease
- another worker cannot claim until the existing lease is expired or released
- expired leases are discoverable through `find_expired_leases()`
- status responses include `worker_lease`

File mode persists a compatibility lease artifact:

```text
worker_lease.json
```

SQLite mode stores leases in:

```text
run_leases
```

SQLite `claim_run`, `renew_lease` and `release_run` use `BEGIN IMMEDIATE` so a single local SQLite writer decides the claim/update atomically.

Lifecycle CLI:

```bash
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite claim --run-id demo --worker-id worker-a --lease-seconds 60
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite renew-lease --run-id demo --worker-id worker-a --lease-seconds 60
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite release --run-id demo --worker-id worker-a
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite expired-leases
```

This is a lease primitive, not a complete task queue.

## Postgres scaffold

`PostgresRunStore` is currently a contract scaffold only. It does not connect to Postgres in core runtime/tests and does not perform real persistence yet.

It supports:

- `safe_run_id(...)`
- `run_dir(...)`
- `artifact_path(...)`
- `metadata()`
- config selection through `build_run_store("postgres", ...)`
- CLI selection through `agent/lifecycle.py --run-store postgres`
- API selection through `FOUNDATION_AGENT_RUN_STORE=postgres`

It intentionally raises `PostgresRunStoreUnavailable` for runtime operations such as:

```text
load_request
save_request
load_report
save_report
load_events
list_runs
claim_run
status
```

This prevents callers from mistaking the scaffold for a production Postgres implementation.

Example config:

```bash
FOUNDATION_AGENT_RUN_STORE=postgres \
FOUNDATION_AGENT_RUN_POSTGRES_DSN=postgresql://user:pass@localhost:5432/myai \
python inference/api_server.py --skip-model-load
```

The above only selects the scaffold until a real Postgres implementation is added.

## Event storage and reads

File store behavior:

- `AgentEventWriter` writes `events.jsonl` under the run directory.
- `FileRunStore.load_events(run_id)` reads that JSONL file.
- `GET /v1/agent/events` reads through the selected run store, so file mode still returns JSONL events.

SQLite store behavior:

- `AgentEventWriter(..., store=sqlite_store)` still writes compatibility `events.jsonl`.
- The same event is also appended to SQLite `run_events` as it is emitted.
- `SQLiteRunStore.load_events(run_id)` reads from the `run_events` table.
- `GET /v1/agent/events` reads SQLite events through the selected store.
- `GET /v1/agent/events?stream=true` polls the selected store, so SQLite mode can stream DB-backed events.

This gives DB-backed event reads without deleting the existing file artifacts.

## File-backed implementation

`FileRunStore` stores each run under:

```text
<output_root>/<run_id>/
```

Current artifact mapping:

```text
agent_request.json       -> request
agent_run_report.json    -> report
events.jsonl             -> events
cancel_requested.json    -> cancellation marker
agent_run_created.json   -> initial created run snapshot
worker_lease.json        -> cooperative worker lease
```

`FileRunStore.list_runs()` scans child directories and reads `agent_run_report.json`. This is suitable for local/dev usage and small run directories, not high-volume production query workloads.

## SQLite-backed implementation

`SQLiteRunStore` is a local database-backed implementation that uses Python standard-library `sqlite3` only. It is intended for single-node/local persistence and testable lifecycle state, not for distributed Postgres-scale coordination.

Required tables are created automatically when the store is constructed:

```text
runs
run_requests
run_reports
run_events
cancel_requests
run_artifacts
run_leases
```

Minimum persisted fields:

```text
runs: run_id, status, created_at, updated_at, completed_at, error
run_requests: run_id, request_json
run_reports: run_id, report_json
run_events: run_id, event_id, event_type, status, created_at, event_json
cancel_requests: run_id, marker_json, created_at
run_artifacts: run_id, name, path, artifact_json
run_leases: run_id, worker_id, lease_json, lease_expires_at, status, updated_at
```

Core operations supported in v1:

- `save_request(run_id, request)` / `load_request(run_id)`
- `save_report(run_id, report)` / `load_report(run_id)`
- `append_event(run_id, event)` / `load_events(run_id)` / `event_summary(run_id)`
- `save_cancel_request(run_id, marker)` / `load_cancel_request(run_id)` / `cancel_requested(run_id)`
- `save_artifact(run_id, name, artifact, path=None)` for database-backed artifact index entries
- `list_runs(...)` with status/owner/project/workspace/parent/query/pagination filters
- worker lease claim/renew/release/expired listing
- `status(run_id)` with the same high-level shape as `FileRunStore.status()` and `run_store.type = "sqlite"`

Missing runs or missing request/report records raise `RunNotFoundError` so callers can treat SQLite and file-backed stores consistently.

## API integration

The API endpoints call lifecycle/run store functions:

- `POST /v1/agent/run`
- `GET /v1/agent/runs`
- `GET /v1/agent/events`
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

The API server selects the store through environment variables:

```text
FOUNDATION_AGENT_RUN_STORE=file|sqlite|postgres
FOUNDATION_AGENT_RUN_DB=outputs/agent_runtime/runs.sqlite
FOUNDATION_AGENT_RUN_POSTGRES_DSN=postgresql://user:pass@host:5432/db
```

Default behavior remains file-backed.

`GET /v1/agent/runs` supports query parameters matching `list_runs(...)`:

```text
GET /v1/agent/runs?status=completed&workspace_id=w1&query=demo&limit=50&offset=0&order=desc
```

`GET /v1/agent/events` reads from the selected run store:

```text
GET /v1/agent/events?run_id=demo
GET /v1/agent/events?run_id=demo&stream=true
```

The JSON response includes `events_source`, `run_store` and `events_path` for debugging compatibility mode.

## Safety

`safe_run_id()` rejects:

- empty ids
- `/`
- `\`
- `..`

This keeps file paths and store keys from path traversal.

## Current limitations

- Implemented runtime stores are `FileRunStore` and local `SQLiteRunStore`.
- `PostgresRunStore` is scaffold-only and raises explicit unavailable errors for runtime operations.
- Runtime still writes compatibility file artifacts.
- File-backed listing scans local run directories and is not intended for large-scale production search.
- SQLite listing uses local SQLite/Python filtering and is not a distributed query service.
- SQLite DB-backed events are local-node events, not a distributed event bus.
- Worker leases are cooperative and local-store based; they are not a full task queue.
- No real Postgres persistence implementation yet.
- No distributed worker scheduler yet.
- SSE is still polling-based, not WebSocket or push-based infrastructure.

## Next steps

- Implement real Postgres persistence using psycopg/asyncpg.
- Add migrations for Postgres run store tables.
- Add full worker queue/dispatcher semantics on top of leases.
- Add richer search indexes if run volume grows.
