# P1 Provider Usage Reconciliation

Provider usage reconciliation compares route-time estimates with provider-returned actual usage.

Implemented files:

- `services/usage_reconciliation.py`
- `tests/test_usage_reconciliation.py`

Integrated files:

- `agent/runtime.py`
- `tests/test_agent_runtime.py`

## Purpose

Routing estimates usage and cost before provider execution. Provider execution can return different actual token usage.

The reconciliation layer records both values so the platform can distinguish:

- route-time estimates
- provider actual usage
- actual cost computed from provider usage and model instance pricing
- fallback when provider actual usage is missing

## Report shape

Agent writes:

```text
provider_usage_reconciliation.json
```

For model tool-loop final provider response, Agent can also write:

```text
provider_usage_reconciliation_final.json
provider_response_final.json
```

The report includes:

- `status`
- `model_id`
- `provider`
- `usage_source`
- `usage.estimated`
- `usage.actual`
- `usage.delta`
- `cost.estimated`
- `cost.actual`
- `cost.delta`
- `summary`
- `warnings`

## Usage source

`usage_source = provider_response` means actual usage came from the provider response.

`usage_source = estimated_fallback` means provider usage was missing or zero, so the route estimate was reused to avoid writing an empty usage record.

## Cost reconciliation

Actual cost is computed with:

```text
services.cost_estimator.estimate_cost_for_usage(actual_usage, model_instance)
```

The reconciled cost object keeps:

- route estimated cost
- actual cost computed from provider usage
- delta
- ratio
- pricing source

## Agent integration

After successful provider execution, Agent runtime:

1. calls provider adapter
2. reconciles provider usage
3. writes `provider_usage_reconciliation.json`
4. writes reconciled `usage` and `cost` back into `provider_response.json`
5. updates run-level `usage`, `cost` and `usage_reconciliation`
6. writes `usage_ledger.jsonl` using reconciled usage/cost

When a model tool loop has a final provider response, Agent also writes final reconciliation artifacts. Current ledger writing is still single-entry for the first provider execution.

## CLI

```bash
python services/usage_reconciliation.py \
  --route-decision outputs/agent_runtime/demo/route_decision.json \
  --provider-response outputs/agent_runtime/demo/provider_response.json \
  --instances configs/model_instance_registry.json \
  --output outputs/agent_runtime/demo/provider_usage_reconciliation.json
```

## Current limitations

- Multi-round model tool-loop usage is not yet aggregated into one total usage record.
- Provider-specific post-billing reconciliation is not implemented.
- Provider invoice reconciliation is not implemented.
- Pricing metadata must be accurate in `configs/model_instance_registry.json`.
- External placeholder model pricing currently resolves to zero until real provider pricing is filled.

## Next steps

- Aggregate usage across all model tool-loop provider rounds.
- Add provider-specific usage adapters when providers expose non-standard billing fields.
- Add workspace-level budget and quota checks using reconciled actual cost.
- Add daily/monthly usage rollups.
