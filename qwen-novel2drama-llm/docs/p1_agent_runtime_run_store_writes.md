# P1 Agent Runtime Run Store Writes

This task wires the Agent runtime into the selected run store without removing the existing file-backed artifacts.

Implemented files:

- `agent/runtime.py`
- `agent/run_store.py`
- `agent/lifecycle.py`
- `tests/test_agent_runtime.py`
- `docs/p1_agent_runtime_run_store_writes.md`

## What changed

`run_agent_once(...)` now accepts an optional runtime store parameter:

```python
run_agent_once(
    project_root,
    request,
    output_dir,
    instances_path=None,
    rules_path=None,
    store=None,
)
```

The runtime intentionally uses duck-typing instead of importing `RunStore` at module import time. This avoids a circular import because `agent/run_store.py` still imports runtime constants/utilities.

When a store is supplied, runtime now indexes:

- request via `store.save_request(...)`
- created run snapshot through `store.save_artifact(..., name="created_run")`
- final report via `store.save_report(...)`
- final artifact paths via `store.save_artifact(...)`
- events into stores that expose `append_event(...)`
- cancellation marker reads through `store.load_cancel_request(...)`

The file output remains intact for compatibility.

## Compatibility behavior

The existing file artifacts are still written:

- `agent_request.json`
- `agent_run_created.json`
- `agent_run_report.json`
- `events.jsonl`
- `usage_ledger.jsonl`
- provider/tool/quota artifacts when present

The run store acts as an index and alternate lifecycle persistence layer. It does not yet replace every file write.

## Cancellation behavior

`apply_cancellation_if_requested(...)` now checks the selected store first when available:

1. `store.load_cancel_request(run_id)`
2. fallback to `<output_dir>/cancel_requested.json`

This lets SQLite-backed lifecycle cancellation be observed by runtime when the runtime is called with the same store.

## Lifecycle integration

`retry_run(...)` and `resume_run(...)` pass the selected store into `run_agent_once(...)`, so child runs are indexed in the same store.

## Tests

New runtime coverage in `tests/test_agent_runtime.py` verifies:

- runtime saves request/report into `SQLiteRunStore`
- runtime indexes final artifacts into store-visible status
- runtime honors a SQLite cancel marker before execution continues

## Current limitations

- Runtime still writes file artifacts for compatibility.
- API events SSE still reads JSONL files.
- Full DB-backed events are a later task.
- Run listing/query is a later task.
- Postgres/distributed run store is not implemented.
- No worker lease/claim semantics are implemented.

## Status flag

```text
P1_agent_runtime_run_store_writes_implemented_v1 = true
```
