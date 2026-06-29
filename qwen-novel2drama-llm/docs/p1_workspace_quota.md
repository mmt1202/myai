# P1 Workspace Budget and Quota

Workspace quota v1 adds a budget and quota control layer for Agent provider execution.

Implemented files:

- `configs/auth/workspace_quotas.example.json`
- `services/quota_store.py`
- `services/workspace_quota.py`
- `tests/test_workspace_quota.py`
- `tests/test_quota_store.py`

Integrated files:

- `agent/runtime.py`
- `tests/test_agent_runtime.py`
- `openapi/foundation_api.openapi.yaml`
- `scripts/check_openapi_contract.py`
- `.github/workflows/foundation-contract-check.yml`

## Purpose

The quota layer prevents a workspace from exceeding configured usage and budget limits before provider execution starts.

It uses route-time estimated usage/cost for preflight checks and reconciled actual usage/cost for post-provider accounting.

## Configuration

Example config:

```text
configs/auth/workspace_quotas.example.json
```

Runtime config path defaults to:

```text
configs/auth/workspace_quotas.json
```

Runtime state path defaults to:

```text
outputs/auth/workspace_quota_state.json
```

Environment variables:

```text
FOUNDATION_WORKSPACE_QUOTA_ENABLED=true
FOUNDATION_WORKSPACE_QUOTAS=configs/auth/workspace_quotas.json
FOUNDATION_WORKSPACE_QUOTA_STATE=outputs/auth/workspace_quota_state.json
```

Quota backend selection:

```text
FOUNDATION_QUOTA_BACKEND=file|sqlite
FOUNDATION_QUOTA_DB=outputs/auth/quota.sqlite
```

Compatibility aliases:

```text
FOUNDATION_WORKSPACE_QUOTA_BACKEND=file|sqlite
FOUNDATION_WORKSPACE_QUOTA_DB=outputs/auth/quota.sqlite
```

Default backend is `file`, which preserves the previous JSON state behavior.

Agent request overrides:

```json
{
  "workspace_id": "dev-workspace",
  "workspace_quota_enabled": true,
  "workspace_quota_config_path": "configs/auth/workspace_quotas.json",
  "workspace_quota_state_path": "outputs/auth/workspace_quota_state.json"
}
```

## Supported limits

Periods:

- `daily`
- `monthly`

Metrics:

- `max_requests`
- `max_input_tokens`
- `max_output_tokens`
- `max_total_tokens`
- `max_cost`

Config precedence:

```text
default -> workspaces.<workspace_id>
```

Workspace overrides deep-merge with default limits.

## Quota store backends

`services/quota_store.py` provides the shared backend interface for rate limit and workspace quota counters.

Implemented backends:

```text
FileQuotaStore
SQLiteQuotaStore
```

Factory helpers:

```python
build_quota_store(kind, rate_limit_state_path=..., workspace_quota_state_path=..., sqlite_path=...)
quota_store_from_env(rate_limit_state_path=..., workspace_quota_state_path=...)
```

SQLite tables:

```text
rate_limit_buckets
workspace_usage
workspace_quota_events
```

Workspace quota uses `workspace_usage` keyed by:

```text
workspace_id + period_key
```

Period keys are UTC calendar windows:

```text
daily:YYYY-MM-DD
monthly:YYYY-MM
```

SQLite writes use `BEGIN IMMEDIATE` around counter updates so one process performs the update atomically within SQLite. This is still local-node SQLite, not a distributed quota service.

## Agent runtime behavior

When quota is enabled, Agent runtime performs:

1. route model and estimate usage/cost
2. check workspace quota with route estimate
3. write `workspace_quota_check.json`
4. deny provider execution if projected usage exceeds configured limits
5. execute provider if quota allows
6. reconcile actual provider usage/cost
7. record actual usage/cost into quota backend
8. write `workspace_quota_usage.json`

Denied runs fail with:

```text
workspace_quota_exceeded
```

Provider execution does not start when preflight is denied.

## Artifacts

Agent run artifacts can include:

- `workspace_quota_check`
- `workspace_quota_usage`

Files:

```text
workspace_quota_check.json
workspace_quota_usage.json
```

The quota backend stores daily/monthly counters and recent event metadata. In file mode, these remain in JSON state. In SQLite mode, counters go into `workspace_usage` and events go into `workspace_quota_events`.

## CLI

Check quota manually:

```bash
python services/workspace_quota.py \
  --config configs/auth/workspace_quotas.json \
  --state outputs/auth/workspace_quota_state.json \
  --workspace-id dev-workspace \
  --usage '{"total_tokens": 1000}' \
  --cost '{"actual": 0.05}'
```

Record usage manually:

```bash
python services/workspace_quota.py \
  --state outputs/auth/workspace_quota_state.json \
  --workspace-id dev-workspace \
  --usage '{"input_tokens": 500, "output_tokens": 500, "total_tokens": 1000}' \
  --cost '{"actual": 0.05}' \
  --record
```

Use SQLite backend:

```bash
FOUNDATION_QUOTA_BACKEND=sqlite \
FOUNDATION_QUOTA_DB=outputs/auth/quota.sqlite \
python services/workspace_quota.py \
  --config configs/auth/workspace_quotas.json \
  --state outputs/auth/workspace_quota_state.json \
  --workspace-id dev-workspace \
  --usage '{"total_tokens": 1000}'
```

Agent CLI:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --execute-provider \
  --workspace-id dev-workspace \
  --workspace-quota-enabled \
  --workspace-quota-config configs/auth/workspace_quotas.json \
  --workspace-quota-state outputs/auth/workspace_quota_state.json
```

## Current limitations

- SQLite backend is local-node SQLite, not a distributed quota service.
- File backend remains process-local and has no cross-process lock.
- Quota is currently integrated into Agent provider execution, not every `/v1/*` API endpoint.
- Provider invoice or external billing reconciliation is not implemented.
- Quota windows are calendar daily/monthly UTC windows, not custom rolling windows.
- No dashboard or alerting layer yet.

## Next steps

- Add Postgres/distributed quota backend.
- Add API middleware-level quota checks for selected scopes.
- Add workspace budget dashboards and rollups.

## Postgres quota backend v1

T013 adds an optional Postgres-backed `QuotaStore` implementation for environments that need quota state outside local files or SQLite. Select it with `FOUNDATION_QUOTA_BACKEND=postgres` (aliases: `postgresql`, `pg`) and provide `FOUNDATION_QUOTA_POSTGRES_DSN`. The schema lives in `migrations/postgres_quota_store.sql` and persists three contract surfaces: rate-limit buckets, workspace usage counters, and workspace quota events.

The dependency profile is intentionally optional (`requirements/postgres-quota.txt`) so core CI does not connect to or require a real Postgres service. Real database tests are DSN-gated by `FOUNDATION_QUOTA_POSTGRES_DSN` and skip when the DSN is absent.

Boundary: this backend is persistence v1 for quota decisions. It is not a complete billing system, not a globally coordinated distributed limiter with cross-region guarantees, and not production-grade billing/revenue accounting.
