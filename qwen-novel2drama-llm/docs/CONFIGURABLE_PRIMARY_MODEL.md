# Configurable Primary Model Foundation

MyAI Foundation must not hard-code any single provider as the only primary model. GPT-class, Claude-class, Gemini-class, DeepSeek, Qwen/DashScope and local models are all model candidates. The selected primary model is configurable by request, project, workspace, task and global defaults.

## Priority order

Model preference resolution uses this order:

```text
request override
> environment override
> project setting
> workspace setting
> task route
> global default
> router scoring fallback
```

## Implemented files

```text
configs/model_routing_policy.json
services/model_preferences.py
inference/model_router.py
configs/model_instance_registry.json
tests/test_model_preferences.py
tests/test_configurable_model_router.py
```

## Runtime configuration

Environment overrides:

```text
FOUNDATION_PRIMARY_MODEL=<model_instance_id>
FOUNDATION_FALLBACK_MODELS=<model_id_1>,<model_id_2>
```

Policy file:

```text
configs/model_routing_policy.json
```

Request override:

```json
{
  "model_id": "external.deepseek.chat",
  "fallback_models": ["external.qwen_dashscope.omni", "local.qwen2_5_1_5b_instruct"],
  "input": [{"type": "text", "text": "hello"}]
}
```

## Task routes

The default policy includes task routes for:

```text
coding
drama
cheap_summary
private
multimodal
```

These are only defaults. A workspace, project or request can override them.

## Guards

Implemented guards:

- privacy guard: `privacy.local_only=true` forces private/local models
- context guard: models are rejected when request usage exceeds `context_window`
- output guard: models are rejected when expected output exceeds `max_output_tokens`
- cost guard: `max_estimated_cost` can reject candidates over budget

## Router output

`route_model()` now returns:

```json
{
  "selected_model_id": "...",
  "fallback_chain": [],
  "model_preferences": {
    "primary_model": "...",
    "fallback_models": [],
    "preferred_model_ids": [],
    "policy_name": "..."
  },
  "policy_hits": []
}
```

## Design rule

GPT-class models can be recommended defaults, but they are not hard-coded. The Foundation is a configurable model gateway and Agent platform, not a wrapper for a single provider.

## Suggested tests

```bash
python -m unittest tests.test_model_preferences tests.test_configurable_model_router tests.test_foundation_core_services tests.test_ci_profiles
```
