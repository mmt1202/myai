# P1 Auth, API Keys and Workspace Scope

This layer adds a lightweight but extensible authorization boundary for foundation runtime APIs.

Implemented files:

- `services/auth.py`
- `configs/auth/api_keys.example.json`
- `tests/test_auth_service.py`
- `inference/api_server.py`

## Default mode

Auth is disabled by default for local development:

```bash
FOUNDATION_AUTH_REQUIRED=false python inference/api_server.py --skip-model-load
```

In this mode, requests without an API key receive an anonymous auth context.

## Enable auth

Set:

```bash
FOUNDATION_AUTH_REQUIRED=true
FOUNDATION_API_KEYS=configs/auth/api_keys.json
```

Then start the server:

```bash
python inference/api_server.py --skip-model-load
```

## API key header

Use:

```text
X-API-Key: your_api_key
X-Workspace-Id: your_workspace_id
```

`X-Workspace-Id` is optional unless the API key has workspace restrictions and you want to bind the request to a specific workspace.

## API key storage

Use `configs/auth/api_keys.example.json` as a template.

The real key store should be saved as:

```text
configs/auth/api_keys.json
```

Do not commit real API keys.

Only SHA-256 hashes should be stored.

Generate a key hash:

```bash
python services/auth.py --hash-key your_real_api_key
```

## Key record

Example:

```json
{
  "key_id": "dev-admin",
  "name": "Development Admin Key",
  "sha256": "replace_with_sha256_of_real_api_key",
  "status": "active",
  "owner_id": "dev-user",
  "workspaces": ["*"],
  "scopes": ["*"],
  "metadata": {"environment": "development"}
}
```

## Scopes

Current endpoint scopes:

- `foundation:read`
- `model:route`
- `model:invoke`
- `memory:read`
- `memory:write`
- `rules:evaluate`
- `skills:read`
- `skills:call`
- `mcp:read`
- `mcp:call`
- `agent:run`

The wildcard scope `*` grants all scopes.

## Public endpoints

These endpoints do not require API keys even when auth is enabled:

- `/health`
- `/v1/health`
- `/docs`
- `/openapi.json`

## Current limitations

- This is API key based auth, not full OAuth/OIDC.
- Key store is file based.
- No key rotation workflow yet.
- No rate limiting yet.
- No request body workspace binding yet.
- No per-provider or per-model quota enforcement yet.

## Next steps

- Add API key generation and rotation helper.
- Add workspace-level budget and quota checks.
- Add request-body workspace binding.
- Add rate limiting.
- Add audit log events for auth decisions.
