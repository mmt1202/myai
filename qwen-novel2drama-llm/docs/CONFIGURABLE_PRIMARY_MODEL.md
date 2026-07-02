# Configurable Primary Model Foundation

MyAI Foundation must not hard-code any single provider as the only primary model. The selected primary model is configurable by request, environment, project, workspace, task and global defaults.

## Priority order

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
services/model_settings_store.py
inference/model_settings_api.py
inference/model_router.py
inference/api_server.py
configs/model_instance_registry.json
```

## Runtime configuration

```text
FOUNDATION_PRIMARY_MODEL=<model_instance_id>
FOUNDATION_FALLBACK_MODELS=<model_id_1>,<model_id_2>
FOUNDATION_MODEL_SETTINGS_STORE=<settings_json_path>
```

Default policy:

```text
configs/model_routing_policy.json
```

Runtime settings store:

```text
outputs/model_settings/model_settings.json
```

The runtime settings store overlays workspace and project settings on top of the default policy.

## Workspace / Project Settings API

```text
GET    /v1/model/settings
GET    /v1/model/settings/workspaces/{workspace_id}
PUT    /v1/model/settings/workspaces/{workspace_id}
DELETE /v1/model/settings/workspaces/{workspace_id}
GET    /v1/model/settings/projects/{project_id}
PUT    /v1/model/settings/projects/{project_id}
DELETE /v1/model/settings/projects/{project_id}
POST   /v1/model/preferences/resolve
POST   /v1/model/route
```

Request body for setting a scope:

```json
{
  "primary_model": "model.primary",
  "fallback_models": ["model.backup"],
  "metadata": {"reason": "workspace default"}
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

- privacy guard
- context guard
- output guard
- cost guard
- safe workspace/project ID guard

## Router output

`route_model()` returns selected model, fallback chain, model preferences and policy hits.

## Design rule

GPT-class models can be recommended defaults, but they are not hard-coded. The Foundation is a configurable model gateway and Agent platform, not a wrapper for a single provider.

## Suggested tests

```bash
python -m unittest tests.test_model_preferences tests.test_model_settings_store tests.test_model_settings_api tests.test_model_settings_api_server tests.test_configurable_model_router tests.test_foundation_core_services tests.test_ci_profiles
```
