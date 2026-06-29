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
- `migrations/postgres_run_store.sql`
- `requirements/postgres-run-store.txt`
- `tests/test_run_store.py`
- `tests/test_sqlite_run_store.py`
- `tests/test_postgres_run_store_contract.py`

## Contract

Implemented stores:

```text
FileRunStore
SQLiteRunStore
PostgresRunStore persistence v1
```

Factories:

```python
file_run_store(output_root)
sqlite_run_store(db_path)
postgres_run_store(dsn=None, output_root=None, connect=False, auto_init=False)
build_run_store(kind, output_root, sqlite_path=None, postgres_dsn=None)
```

Supported kinds:

```text
file
sqlite
sqlite3
postgres
postgresql
pg
```

Default behavior remains file-backed. SQLite defaults to `<output_root>/runs.sqlite`.

Postgres uses:

```text
FOUNDATION_AGENT_RUN_POSTGRES_DSN
```

The DSN value must be supplied by environment or by `postgres_dsn`; do not commit it.

## Core operations

The run store contract includes:

- request/report load and save
- event append/read/summary
- cancel marker load and save
- artifact index save
- run listing/query
- worker lease claim/renew/release/expired listing
- status and metadata

## File store

`FileRunStore` stores one directory per run:

```text
<output_root>/<run_id>/
```

Compatibility artifacts:

```text
agent_request.json
agent_run_report.json
events.jsonl
cancel_requested.json
agent_run_created.json
worker_lease.json
```

File listing scans local directories and is intended for local/dev workloads.

## SQLite store

`SQLiteRunStore` uses standard-library `sqlite3`. Tables:

```text
runs
run_requests
run_reports
run_events
cancel_requests
run_artifacts
run_leases
```

SQLite is local-node persistence, not a distributed store.

## Postgres store

`PostgresRunStore` now implements real persistence for the same contract using optional `psycopg` dependency.

Dependency profile:

```bash
python -m pip install -r requirements/postgres-run-store.txt
```

Schema migration:

```text
migrations/postgres_run_store.sql
```

The schema defines:

```text
runs
run_requests
run_reports
run_events
cancel_requests
run_artifacts
run_leases
```

Runtime methods implemented:

- `init_db()`
- `save_request()` / `load_request()`
- `save_report()` / `load_report()`
- `append_event()` / `load_events()` / `event_summary()`
- `save_cancel_request()` / `load_cancel_request()` / `cancel_requested()`
- `save_artifact()`
- `list_runs(...)`
- `claim_run()` / `renew_lease()` / `release_run()` / `find_expired_leases()`
- `status()`

Postgres worker lease operations use `SELECT ... FOR UPDATE` around the lease row so one transaction decides claim/renew/release for that run.

`PostgresRunStore` is optional. Core CI imports the module without installing psycopg; real DB behavior is tested only through the optional profile and DSN-gated test.

## CI profiles

Core CI does not install Postgres dependencies and does not connect to a database.

Optional profile:

```bash
python scripts/ci_profiles.py --profile postgres-run-store
python -m unittest tests.test_postgres_run_store_contract
```

Standalone workflow:

```text
.github/workflows/foundation-postgres-run-store.yml
```

The real database contract test is skipped unless `FOUNDATION_AGENT_RUN_POSTGRES_DSN` is configured.

## API integration

API server store selection:

```text
FOUNDATION_AGENT_RUN_STORE=file|sqlite|postgres
FOUNDATION_AGENT_RUN_DB=<sqlite db path>
FOUNDATION_AGENT_RUN_POSTGRES_DSN=<configured outside git>
```

Endpoints using the selected store:

- `POST /v1/agent/run`
- `GET /v1/agent/runs`
- `GET /v1/agent/events`
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

## Worker leases

Rules:

- one active lease per run
- same worker can renew
- another worker can claim only after expiration or release
- expired leases are discoverable
- status includes `worker_lease`

File mode writes `worker_lease.json`; SQLite writes `run_leases`; Postgres writes `run_leases` and uses row locks.

## Safety

`safe_run_id()` rejects empty ids, path separators and `..`.

## Current limitations

- Postgres persistence v1 is implemented, but migrations are SQL-file based; there is no migration runner yet.
- No connection pool management beyond psycopg connection creation.
- Real Postgres tests require external DSN configuration and are not part of default core CI.
- Worker leases are still cooperative and not a full task queue.
- Runtime still writes compatibility file artifacts.
- SSE is polling-based, not WebSocket or push event infrastructure.
- No full distributed worker scheduler yet.

## Next steps

- Add a migration runner.
- Add connection pooling and production deployment profile.
- Add full worker queue/dispatcher semantics on top of leases.
- Add richer query indexes and retention policies.
