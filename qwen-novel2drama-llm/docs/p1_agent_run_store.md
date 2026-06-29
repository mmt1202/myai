# P1 Agent Run Store

This layer introduces a replaceable run store contract for Agent run state, event reads, run listing, lifecycle state, worker leases and local queue dispatching.

Implemented files:

- `agent/run_store.py`
- `agent/sqlite_run_store.py`
- `agent/postgres_run_store.py`
- `agent/postgres_migration_history.py`
- `agent/worker_dispatcher.py`
- `agent/events.py`
- `agent/runtime.py`
- `agent/lifecycle.py`
- `inference/api_server.py`
- `migrations/postgres_run_store.sql`
- `scripts/apply_postgres_run_store_migration.py`
- `configs/run_store/postgres.example.env`
- `requirements/postgres-run-store.txt`
- `tests/test_run_store.py`
- `tests/test_sqlite_run_store.py`
- `tests/test_postgres_run_store_contract.py`
- `tests/test_worker_dispatcher.py`

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
postgres_run_store(dsn=None, output_root=None, connect=False, auto_init=False, connection_profile=None)
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

## Core operations

The run store contract includes request/report load and save, event append/read/summary, cancel markers, artifact indexes, run listing/query, worker lease claim/renew/release, status and metadata.

## Postgres store

`PostgresRunStore` implements persistence for the same contract using the optional Postgres dependency profile.

Dependency profile:

```bash
python -m pip install -r requirements/postgres-run-store.txt
```

Schema migration file:

```text
migrations/postgres_run_store.sql
```

Migration runner:

```bash
python scripts/apply_postgres_run_store_migration.py --dry-run --json
python scripts/apply_postgres_run_store_migration.py --json
```

The migration runner records applied migrations in:

```text
schema_migrations
```

Each record stores `migration_id`, `checksum`, `statement_count`, `applied_at` and metadata. Reapplying the same SQL is idempotent; applying the same migration id with a different checksum raises a conflict.

Postgres worker lease operations use `SELECT ... FOR UPDATE` around the lease row so one transaction decides claim/renew/release for that run.

## Worker dispatcher

`agent/worker_dispatcher.py` adds a local dispatcher on top of the RunStore and worker lease contract.

Commands:

```bash
python agent/worker_dispatcher.py enqueue --request examples/agent_request.json --run-id queued-demo
python agent/worker_dispatcher.py list
python agent/worker_dispatcher.py dispatch --worker-id worker-a --max-runs 5
```

Capabilities:

- enqueue request/report into selected run store
- list queued runs
- claim one queued run using worker lease
- execute the run through `run_agent_once(...)`
- release the worker lease
- dispatch multiple runs with `dispatch_loop(...)`
- track queue attempts
- mark dead-letter runs as failed after max attempts

This is a cooperative dispatcher and local queue abstraction, not an external queue service.

## Postgres connection profile

Example config file:

```text
configs/run_store/postgres.example.env
```

Connection pool env:

```text
FOUNDATION_AGENT_RUN_POSTGRES_POOL_ENABLED=false
FOUNDATION_AGENT_RUN_POSTGRES_POOL_MIN=1
FOUNDATION_AGENT_RUN_POSTGRES_POOL_MAX=5
FOUNDATION_AGENT_RUN_POSTGRES_POOL_TIMEOUT=30
```

When pool mode is enabled, `PostgresRunStore` lazily creates a `psycopg_pool.ConnectionPool`. Call `close()` during shutdown to close the pool.

## CI profiles

Core CI includes dispatcher tests and does not install Postgres dependencies.

Optional profile:

```bash
python scripts/ci_profiles.py --profile postgres-run-store
python -m unittest tests.test_postgres_run_store_contract
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

## Current limitations

- Connection pool config exists, but there is no full production deployment profile or health-check endpoint yet.
- Worker dispatcher is cooperative and not an external distributed queue service.
- Runtime still writes compatibility file artifacts.
- SSE is polling-based, not WebSocket or push event infrastructure.
- No cross-service distributed scheduler yet.

## Next steps

- Add production deployment profile and pool health checks.
- Add dashboard/observability for queue lag, failed runs and worker health.
- Add richer query indexes and retention policies.
