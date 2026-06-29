# P1 Hardening

This document tracks production hardening work after the P1 foundation runtime was made functional.

## Implemented hardening files

- `inference/api_server.py`
- `providers/session_lifecycle.py`
- `agent/postgres_db_ops.py`
- `services/billing_limits.py`
- `Dockerfile`
- `compose.production.yml`
- `configs/deploy/production.example.env`
- `tests/test_api_server_foundation.py`
- `tests/test_provider_session_lifecycle.py`
- `tests/test_postgres_db_ops.py`
- `tests/test_billing_limits.py`

## H001 API middleware-level quota checks

`inference/api_server.py` now includes an API-level workspace quota preflight in the HTTP middleware.

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

Boundary: this is API request-level quota enforcement. It is not full billing and does not replace provider actual-usage reconciliation.

## H002 Production deployment profile

Production-like deployment artifacts:

```text
Dockerfile
compose.production.yml
configs/deploy/production.example.env
```

The deployment profile includes:

- API container
- Postgres service
- persistent `outputs` volume
- root `/v1/ready` healthcheck
- Postgres-backed run store/quota store env template

Boundary: this is a production-like profile, not a complete cloud deployment, autoscaling, TLS, secret manager or backup system.

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

Boundary: readiness reports component health; it does not perform destructive DB probes or real provider calls.

## H004 Pool health checks

Postgres run store pool metadata is surfaced through the run store component in `/v1/ready` and `/v1/health/deep`.

Boundary: pool status is metadata/readiness level. It is not a full connection-pool metrics exporter.

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

Boundary: this is queue observability for the internal dispatcher. It is not an external message queue UI or worker-pool orchestrator.

## H006 Provider session lifecycle hardening

`providers/session_lifecycle.py` defines:

- `ProviderSessionState`
- valid status transitions
- lifecycle transition validation
- session health summary

Boundary: this is a lifecycle contract used by provider session adapters. It does not own browser, WebRTC, SIP or audio-device session setup.

## H007 Migration rollback / DB ops hardening

`agent/postgres_db_ops.py` defines:

- forward migration planning
- manual rollback plan generation
- DB ops health summary

Boundary: rollback is intentionally manual-review only. The project records migration history and plans rollback but does not execute automatic down migrations.

## H008 Billing / global rate limit hardening

`services/billing_limits.py` defines:

- billing limit readiness plan
- global rate-limit health summary
- billing reconciliation status

Boundary: Postgres quota provides shared persistence for quota decisions, not complete billing, invoice reconciliation, or globally strongly-consistent distributed rate limiting.

## Suggested tests

```bash
python -m unittest tests.test_api_server_foundation tests.test_provider_session_lifecycle tests.test_postgres_db_ops tests.test_billing_limits tests.test_ci_profiles
```
