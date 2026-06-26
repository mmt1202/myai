# P1 Rule Engine

The rule engine is a deterministic foundation service for policy decisions.

Rules should not be hidden inside prompts. They must be inspectable, testable and auditable.

Implemented files:

- `configs/rules/default_rules.yaml`
- `services/rule_engine.py`
- `tests/test_rule_engine.py`

## Decisions

Supported effects:

- `allow`
- `review`
- `deny`

When multiple rules match, the strongest effect wins:

```text
allow < review < deny
```

## Operators

Supported condition operators:

- `exists`
- `missing`
- `equals`
- `not_equals`
- `contains`
- `not_contains`
- `greater_than`
- `less_than`

## Default rules

Initial default rules cover:

- local-only privacy blocks external providers
- budget limit blocks expensive candidates
- secret data with external provider requires review
- source-changing tools require review
- secret memory requires owner scope
- deprecated models require review
- drama specialist mode should use reasoning-capable models

## Evaluate rules

```bash
python services/rule_engine.py \
  --rules configs/rules/default_rules.yaml \
  --context examples/rule_context.json
```

Example context:

```json
{
  "request": {
    "privacy": {"local_only": true},
    "budget": {"max_estimated_cost": 0.01}
  },
  "candidate": {
    "provider": "openai_compatible",
    "estimated_cost": {"estimated": 0.02}
  }
}
```

## Current limitations

- The YAML loader supports only the current ruleset shape.
- No remote policy backend yet.
- No full conflict analyzer yet.
- No API server integration yet.

## Next steps

- Integrate rule evaluation into `model_router.py`.
- Add rule hit metadata to response envelope route logs.
- Add approval workflow integration in agent runtime.
- Add provider, region and workspace-level policy overlays.
