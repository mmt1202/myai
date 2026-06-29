# P1 Hardening

This document tracks production hardening work after the P1 foundation runtime was made functional.

## Implemented hardening files

- `inference/api_server.py`
- `providers/session_lifecycle.py`
- `services/secret_resolver.py`
- `services/metrics.py`
- `agent/worker_pool.py`
- `agent/postgres_db_ops.py`
- `scripts/postgres_backup.py`
- `scripts/production_preflight.py`
- `services/billing_limits.py`
- `Dockerfile`
- `compose.production.yml`
- `configs/deploy/production.example.env`
- `configs/deploy/nginx.tls.example.conf`
- `tests/test_api_server_foundation.py`
- `tests/test_provider_session_lifecycle.py`
- `tests/test_secret_resolver.py`
- `tests/test_metrics.py`
- `tests/test_worker_pool.py`
- `tests/test_postgres_db_ops.py`
- `tests/test_postgres_backup.py`
- `tests/test_production_preflight.py`
- `tests/test_billing_limits.py`

## H001 API middleware-level quota checks

`inference/api_server.py` includes an API-level workspace quota preflight in the HTTP middleware.

Configuration:

```text
FOUNDATION_API_QUOTA_ENABLED=true
FOUNDATION_API_QUOTA_PATHS=/v1/chat,/v1/reason,/v1/multimodal/analyze,/v1/agent/run
```

Behavior:

- disabled by default
- applies only to configured write-like API paths
- estimates request usage from the body when explicit usage is not supplied
- checks workspace quota before endpoint execution
- returns `workspace_quota_exceeded` with quota headers when denied
- records request-level usage after successful responses

## H002 Production deployment profile

Production-like deployment artifacts:

```text
Dockerfile
compose.production.yml
configs/deploy/production.example.env
configs/deploy/nginx.tls.example.conf
```

The deployment profile includes:

- API container
- worker pool profile
- preflight profile
- optional nginx TLS reverse proxy profile
- Postgres service
- persistent `outputs` volume
- `/v1/ready` healthcheck
- Postgres-backed run store/quota store env template

Commands:

```bash
docker compose -f compose.production.yml --profile preflight run --rm preflight
docker compose -f compose.production.yml up api postgres
docker compose -f compose.production.yml --profile worker up worker
docker compose -f compose.production.yml --profile tls up nginx
```

## H003 Health checks / readiness checks

API endpoints:

```text
GET /health
GET /v1/health
GET /v1/ready
GET /v1/health/deep
```

Deep readiness checks include:

- local model state
- run store metadata
- quota backend metadata
- provider registry availability
- queue summary

## H004 Pool health checks

Postgres run store pool metadata is surfaced through the run store component in `/v1/ready` and `/v1/health/deep`.

## H005 Queue observability

API endpoint:

```text
GET /v1/agent/queue
```

Returns:

- run store metadata
- counts by status
- queued/running/failed/completed/cancelled samples
- dead-letter count

## H006 Provider session lifecycle hardening

`providers/session_lifecycle.py` defines:

- `ProviderSessionState`
- valid status transitions
- lifecycle transition validation
- session health summary

## H007 Migration rollback / DB ops hardening

`agent/postgres_db_ops.py` defines:

- forward migration planning
- manual rollback plan generation
- DB ops health summary

`script/postgres_backup.py` provides backup and restore command planning and optional execution without printing DSN values.

## H008 Billing / global rate limit hardening

`services/billing_limits.py` defines:

- billing limit readiness plan
- global rate-limit health summary
- billing reconciliation status

## H009 Secret management contract

`services/secret_resolver.py` supports production-safe secret references:

```text
env:NAME
file:/path/to/secret
literal:development-only-value
```

Raw secret values are rejected by default. Health checks can report whether secret references are configured without printing secret values.

## H010 Metrics exporter contract

`services/metrics.py` provides a lightweight Prometheus text renderer and runtime metric sample contract for readiness and queue metrics.

## H011 Worker pool

`agent/worker_pool.py` runs repeated dispatcher iterations over the internal queue with configurable worker count, idle stop and lease settings.

## H012 Backup / restore automation

`scripts/postgres_backup.py` provides:

```bash
python scripts/postgres_backup.py backup --path outputs/backups/foundation.dump
python scripts/postgres_backup.py restore --path outputs/backups/foundation.dump
```

Default behavior is planning only. `--execute` runs `pg_dump` or `pg_restore` using a configured DSN env var without printing the DSN.

## H013 Production preflight

`scripts/production_preflight.py` verifies:

- required production files exist
- hardening flags are present in `docs/implementation_status.md`
- env template does not contain unsafe secret values

## H014 TLS / reverse proxy template

`configs/deploy/nginx.tls.example.conf` provides a TLS reverse proxy template for `/`, `/health`, `/v1/ready` and `/metrics`.

## Current boundaries

- This is a complete repository-level hardening loop, not a managed cloud platform.
- TLS material, real secrets, backups and autoscaling must be provided by the deployment environment.
- Global strong consistency still requires external limiter/database operational guarantees.
- Provider realtime browser/WebRTC/SIP connection ownership is still outside the foundation process.

## Suggested tests

```bash
python -m unittest tests.test_api_server_foundation tests.test_provider_session_lifecycle tests.test_secret_resolver tests.test_metrics tests.test_worker_pool tests.test_postgres_db_ops tests.test_postgres_backup tests.test_production_preflight tests.test_billing_limits tests.test_ci_profiles
```
