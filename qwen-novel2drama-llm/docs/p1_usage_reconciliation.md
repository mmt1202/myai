# P1 Provider Usage Reconciliation

Provider usage reconciliation compares route-time estimates with provider-returned actual usage.

Implemented files:

- `services/usage_reconciliation.py`
- `services/model_tool_loop_usage.py`
- `tests/test_usage_reconciliation.py`
- `tests/test_model_tool_loop_usage.py`

Integrated files:

- `agent/runtime.py`
- `agent/tool_loop.py`
- `tests/test_agent_runtime.py`
- `.github/workflows/foundation-contract-check.yml`

## Purpose

Routing estimates usage and cost before provider execution. Provider execution can return different actual token usage.

The reconciliation layer records both values so the platform can distinguish:

- route-time estimates
- provider actual usage
- actual cost computed from provider usage and model instance pricing
- fallback when provider actual usage is missing
- aggregated usage/cost across multi-round model tool loops

## Report shape

Agent writes:

```text
provider_usage_reconciliation.json
```

For model tool-loop final provider response, Agent can also write:

```text
provider_usage_reconciliation_final.json
provider_response_final.json
model_tool_loop_usage_aggregation.json
```

The provider reconciliation report includes:

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

The model tool-loop aggregation report includes:

- `provider_call_count`
- `usage`
- `cost`
- `provider_calls`
- `by_model`
- `by_provider`
- `warnings`
- `missing_usage_sources`

## Usage source

`usage_source = provider_response` means actual usage came from the provider response.

`usage_source = estimated_fallback` means provider usage was missing or zero, so the route estimate was reused to avoid writing an empty usage record.

For model tool-loop aggregation, `usage_source = missing_or_zero` marks a provider call whose response had no usable usage signal. That call contributes zero usage and is listed in `missing_usage_sources`.

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

Model tool-loop aggregation sums actual/estimated cost across all provider calls. If a provider response includes a cost object, that amount is used; otherwise the cost is estimated from the provider call usage and model instance pricing.

## Agent integration

After successful provider execution, Agent runtime:

1. calls provider adapter
2. reconciles provider usage
3. writes `provider_usage_reconciliation.json`
4. writes reconciled `usage` and `cost` back into `provider_response.json`
5. updates run-level `usage`, `cost` and `usage_reconciliation`
6. writes `usage_ledger.jsonl` using reconciled usage/cost

When a model tool loop runs, `agent/tool_loop.py` now:

1. keeps the initial provider response in `model_tool_loop.json`
2. collects every follow-up provider response from `rounds[*].provider_response`
3. writes `model_tool_loop_usage_aggregation.json`
4. attaches `usage_aggregation` to `model_tool_loop.json`
5. writes aggregated `usage` and `cost` back to the final provider response

Because the final provider response carries aggregate usage, Agent runtime final reconciliation sees the model tool loop total rather than only the last provider call.

## CLI

Single provider response reconciliation:

```bash
python services/usage_reconciliation.py \
  --route-decision outputs/agent_runtime/demo/route_decision.json \
  --provider-response outputs/agent_runtime/demo/provider_response.json \
  --instances configs/model_instance_registry.json \
  --output outputs/agent_runtime/demo/provider_usage_reconciliation.json
```

Model tool-loop aggregation:

```bash
python services/model_tool_loop_usage.py \
  --initial-provider-response outputs/agent_runtime/demo/provider_response.json \
  --model-tool-loop outputs/agent_runtime/demo/model_tool_loop.json \
  --instances configs/model_instance_registry.json \
  --selected-model-id external.openai_compatible.smart \
  --output outputs/agent_runtime/demo/model_tool_loop_usage_aggregation.json
```

## Current limitations

- Aggregation is file/artifact based, not a provider billing reconciliation job.
- Missing provider usage contributes zero usage for that provider call and emits a warning.
- Provider invoice reconciliation is not implemented.
- Pricing metadata must be accurate in `configs/model_instance_registry.json`.
- External placeholder model pricing currently resolves to zero until real provider pricing is filled.
- Same-stream tool-result injection is not implemented.

## Next steps

- Add provider-specific usage adapters when providers expose non-standard billing fields.
- Add provider invoice/billing reconciliation.
- Add daily/monthly usage rollups.
- Add same-stream tool-result injection when provider protocols support it.
