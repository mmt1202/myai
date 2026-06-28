# P1 Agent Run Store

This layer introduces a replaceable run store contract for Agent run state.

Implemented files:

- `agent/run_store.py`
- `agent/sqlite_run_store.py`
- `agent/lifecycle.py`
- `inference/api_server.py`
- `tests/test_run_store.py`
- `tests/test_sqlite_run_store.py`
- `tests/test_agent_lifecycle.py`
- `tests/test_api_server_foundation.py`

## Purpose

Before this layer, Agent lifecycle code read and wrote these files directly:

- `agent_request.json`
- `agent_run_report.json`
- `events.jsonl`
- `cancel_requested.json`

The run store abstraction makes those operations explicit so a future database-backed store can replace the file-backed implementation without rewriting lifecycle APIs.

## Contract

Base interface:

```text
RunStore
```

Implemented stores:

```text
FileRunStore
SQLiteRunStore
```

Factories:

```python
file_run_store(output_root)
sqlite_run_store(db_path)
build_run_store(kind, output_root, sqlite_path=None)
```

Supported run store kinds:

```text
file
sqlite
sqlite3
```

`build_run_store()` defaults to file-backed storage. For SQLite, the default database path is:

```text
<output_root>/runs.sqlite
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
- `status(run_id)`
- `metadata()`

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
```

`FileRunStore.status(run_id)` returns:

```json
{
  "run_id": "demo",
  "status": "completed",
  "error": null,
  "created_at": "...",
  "updated_at": "...",
  "completed_at": "...",
  "cancel_requested": false,
  "artifacts": {},
  "event_summary": {},
  "run_store": {
    "type": "file",
    "output_root": "outputs/agent_runtime/api"
  }
}
```

## SQLite-backed implementation

`SQLiteRunStore` is a local database-backed implementation that uses Python standard-library `sqlite3` only. It is intended for single-node/local persistence and testable lifecycle state, not for distributed leases or Postgres-scale coordination.

Factory:

```python
sqlite_run_store(db_path)
```

Required tables are created automatically when the store is constructed:

```text
runs
run_requests
run_reports
run_events
cancel_requests
run_artifacts
```

Minimum persisted fields:

```text
runs: run_id, status, created_at, updated_at, completed_at, error
run_requests: run_id, request_json
run_reports: run_id, report_json
run_events: run_id, event_id, event_type, status, created_at, event_json
cancel_requests: run_id, marker_json, created_at
run_artifacts: run_id, name, path, artifact_json
```

Core operations supported in v1:

- `save_request(run_id, request)` / `load_request(run_id)`
- `save_report(run_id, report)` / `load_report(run_id)`
- `append_event(run_id, event)` / `load_events(run_id)` / `event_summary(run_id)`
- `save_cancel_request(run_id, marker)` / `load_cancel_request(run_id)` / `cancel_requested(run_id)`
- `save_artifact(run_id, name, artifact, path=None)` for database-backed artifact index entries
- `status(run_id)` with the same high-level shape as `FileRunStore.status()` and `run_store.type = "sqlite"`

Missing runs or missing request/report records raise `RunNotFoundError` so callers can treat SQLite and file-backed stores consistently.

## Lifecycle integration

`agent/lifecycle.py` routes through a selected run store while preserving its public function signatures:

- `status_run(output_root, run_id, store=None)`
- `cancel_run(output_root, run_id, ..., store=None)`
- `retry_run(project_root=..., output_root=..., run_id=..., ..., store=None)`
- `resume_run(project_root=..., output_root=..., run_id=..., ..., store=None)`

The optional `store` parameter is the compatibility seam for future database-backed implementations.

CLI selection:

```bash
python agent/lifecycle.py --run-store file --output-root outputs/agent_runtime/api status --run-id demo
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite status --run-id demo
```

## API integration

The API endpoints continue to call lifecycle functions:

- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

The API server selects the store through environment variables:

```text
FOUNDATION_AGENT_RUN_STORE=file|sqlite
FOUNDATION_AGENT_RUN_DB=outputs/agent_runtime/runs.sqlite
```

Default behavior remains file-backed.

When `/v1/agent/run` completes, the API server indexes the request/report into the selected run store with `index_run_in_store()`. This makes `GET /v1/agent/status` work for SQLite-backed runs before the full runtime artifact migration is implemented.

## Safety

`safe_run_id()` rejects:

- empty ids
- `/`
- `\`
- `..`

This keeps file paths and store keys from path traversal.

## Current limitations

- Implemented stores are `FileRunStore` and local `SQLiteRunStore`.
- API/lifecycle can select SQLite, but runtime artifact writes still primarily use file paths directly.
- API Agent events still read JSONL files; full DB-backed event streaming is a later task.
- No Postgres implementation yet; SQLite is local-only and not distributed.
- No transaction, lock, lease or distributed concurrency control yet.
- No run listing/query index yet.

## Next steps

- Migrate runtime artifact writes to the store interface.
- Add run listing and query filters.
- Add DB-backed Agent events and lifecycle status reads.
- Add locking/lease semantics for distributed workers.
- Add Postgres run store implementation.
