# P1 Workspace Budget and Quota

Workspace quota v1 adds a file-backed budget and quota control layer for Agent provider execution.

Implemented files:

- `configs/auth/workspace_quotas.example.json`
- `services/workspace_quota.py`
- `tests/test_workspace_quota.py`

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

## Agent runtime behavior

When quota is enabled, Agent runtime performs:

1. route model and estimate usage/cost
2. check workspace quota with route estimate
3. write `workspace_quota_check.json`
4. deny provider execution if projected usage exceeds configured limits
5. execute provider if quota allows
6. reconcile actual provider usage/cost
7. record actual usage/cost into quota state
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

The quota state stores daily/monthly counters and a bounded recent event list.

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

- State is file-backed and process-local, not distributed.
- No locking is implemented for concurrent writers.
- Quota is currently integrated into Agent provider execution, not every `/v1/*` API endpoint.
- Multi-round model tool-loop usage is not aggregated into quota as one total yet.
- Provider invoice or external billing reconciliation is not implemented.
- Quota windows are calendar daily/monthly UTC windows, not custom rolling windows.

## Next steps

- Add distributed quota backend.
- Add multi-round model tool-loop usage aggregation.
- Add API middleware-level quota checks for selected scopes.
- Add workspace budget dashboards and rollups.
