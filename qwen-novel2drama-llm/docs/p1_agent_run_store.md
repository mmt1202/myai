# P1 Agent Run Store

This layer introduces a replaceable run store contract for Agent run state.

Implemented files:

- `agent/run_store.py`
- `agent/lifecycle.py`
- `tests/test_run_store.py`
- `tests/test_agent_lifecycle.py`
- `tests/test_api_server_foundation.py`

## Purpose

Before this layer, Agent lifecycle code read and wrote these files directly:

- `agent_request.json`
- `agent_run_report.json`
- `events.jsonl`
- `cancel_requested.json`

The new run store abstraction makes those operations explicit so a future database-backed store can replace the file-backed implementation without rewriting lifecycle APIs.

## Contract

Base interface:

```text
RunStore
```

Current implementation:

```text
FileRunStore
```

Factory:

```python
file_run_store(output_root)
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

## Lifecycle integration

`agent/lifecycle.py` now routes through `FileRunStore` while preserving its existing public function signatures:

- `status_run(output_root, run_id, store=None)`
- `cancel_run(output_root, run_id, ..., store=None)`
- `retry_run(project_root=..., output_root=..., run_id=..., ..., store=None)`
- `resume_run(project_root=..., output_root=..., run_id=..., ..., store=None)`

The optional `store` parameter is the compatibility seam for future database-backed implementations.

## API integration

The API endpoints continue to call lifecycle functions:

- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

Because lifecycle functions now use the run store abstraction, those APIs are already aligned with the store boundary.

## Safety

`safe_run_id()` rejects:

- empty ids
- `/`
- `\`
- `..`

This keeps the file-backed store from path traversal.


## SQLite-backed implementation

`SQLiteRunStore` is a local database-backed implementation that uses Python standard-library `sqlite3` only. It is intended for single-node/local persistence and testable lifecycle state, not for distributed leases or Postgres-scale coordination.

Implemented files:

- `agent/sqlite_run_store.py`
- `tests/test_sqlite_run_store.py`

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

Current SQLite limitations:

- `SQLiteRunStore` is implemented but not yet wired into CLI/API run-store selection; that is a later task.
- Runtime artifact writes still primarily use file paths directly.
- This is not a distributed run store and does not provide cross-process leases, worker ownership, queueing, or Postgres compatibility.

## Current limitations

- Implemented stores are `FileRunStore` and local `SQLiteRunStore`.
- Runtime writes still use file paths directly; lifecycle reads/writes now go through the store abstraction.
- No Postgres implementation yet; SQLite is local-only and not distributed.
- No transaction, lock, lease or distributed concurrency control yet.
- No run listing/query index yet.
- Event streaming still reads JSONL files.

## Next steps

- Wire `SQLiteRunStore` into CLI/API run-store selection.
- Add run listing and query filters.
- Migrate runtime artifact writes to the store interface.
- Add DB-backed Agent events and lifecycle status reads.
- Add locking/lease semantics for distributed workers.
