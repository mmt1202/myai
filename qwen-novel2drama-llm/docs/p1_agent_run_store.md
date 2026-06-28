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

## Current limitations

- The only implemented store is `FileRunStore`.
- Runtime writes still use file paths directly; lifecycle reads/writes now go through the store abstraction.
- No SQLite/Postgres implementation yet.
- No transaction, lock, lease or distributed concurrency control yet.
- No run listing/query index yet.
- Event streaming still reads JSONL files.

## Next steps

- Add `SQLiteRunStore` as a local database-backed implementation.
- Add run listing and query filters.
- Migrate runtime artifact writes to the store interface.
- Add DB-backed Agent events and lifecycle status reads.
- Add locking/lease semantics for distributed workers.
