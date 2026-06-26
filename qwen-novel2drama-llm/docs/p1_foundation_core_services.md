# P1 Foundation Core Services

This layer begins turning the P0 foundation contracts into runtime services.

Implemented service modules:

- `inference/model_router.py`
- `services/token_counter.py`
- `services/cost_estimator.py`
- `services/usage_ledger.py`

These are service v1 implementations. They are not final production-grade provider integrations.

## Token counter

```bash
python services/token_counter.py --request examples/request.json
```

Current estimator:

- text token heuristic
- CJK-aware heuristic
- image billable units by megapixel
- video billable seconds
- audio billable seconds
- memory/rules token estimate

The estimator is intentionally provider-neutral. Later provider adapters can reconcile actual provider usage.

## Cost estimator

```bash
python services/cost_estimator.py \
  --request examples/request.json \
  --model-id local.qwen2_5_1_5b_instruct
```

It reads pricing metadata from:

```text
configs/model_instance_registry.json
```

Supported cost dimensions:

- input tokens
- output tokens
- image units
- video seconds
- audio seconds

## Usage ledger

```bash
python services/usage_ledger.py --event outputs/usage/event.json
python services/usage_ledger.py --summary
```

The ledger writes JSONL events and summarizes:

- events
- input tokens
- output tokens
- reasoning tokens
- total tokens
- estimated cost
- actual cost
- by model
- by provider

## Model router

```bash
python inference/model_router.py --request examples/request.json
```

The router uses:

- `configs/model_capability_registry.json`
- `configs/model_instance_registry.json`
- route mode policy from `configs/model_router.yaml`

Runtime routing currently implements:

- required capability filtering
- required modality filtering
- local-only privacy filtering
- context window filtering
- deprecated model filtering
- route-mode scoring
- fallback chain generation
- route decision log output

Initial route modes:

- `smart`
- `cheap`
- `balanced`
- `local_first`
- `cloud_first`
- `drama_specialist`
- `code_specialist`

## Current limitations

- Token estimates are heuristic until provider-specific tokenizers are integrated.
- Provider actual usage reconciliation is not implemented yet.
- Model quality scores are rule-based placeholders until evaluation scores exist.
- Router does not yet call providers; it only selects model instances.
- Router config is contract-first; runtime uses built-in matching weights for now.

## Next steps

- Add provider adapter base interface.
- Add OpenAI-compatible provider adapter.
- Add actual usage reconciliation.
- Add evaluation-backed model quality scores.
- Add request/response integration into `inference/api_server.py`.
