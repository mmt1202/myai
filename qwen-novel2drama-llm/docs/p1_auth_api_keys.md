# P1 Auth, API Keys and Workspace Scope

This layer adds a lightweight but extensible authorization boundary for foundation runtime APIs.

Implemented files:

- `services/auth.py`
- `services/auth_audit.py`
- `services/rate_limiter.py`
- `services/quota_store.py`
- `configs/auth/api_keys.example.json`
- `configs/auth/rate_limits.example.json`
- `tests/test_auth_service.py`
- `tests/test_auth_audit_rate_limit.py`
- `tests/test_quota_store.py`
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

`agent:run` covers:

- `POST /v1/agent/run`
- `GET /v1/agent/runs`
- `GET /v1/agent/events`
- `GET /v1/agent/status`
- `POST /v1/agent/cancel`
- `POST /v1/agent/retry`
- `POST /v1/agent/resume`

## Audit log

The API middleware writes auth events to:

```text
outputs/auth/auth_audit.jsonl
```

Events include:

- decision
- key id
- owner id
- workspace id
- required scope
- method
- path
- status code
- reason
- client host

Read or summarize the log:

```bash
python services/auth_audit.py --log outputs/auth/auth_audit.jsonl
python services/auth_audit.py --log outputs/auth/auth_audit.jsonl --summary
```

## Rate limiting

Rate limiting is disabled by default.

Enable it with:

```bash
FOUNDATION_RATE_LIMIT_ENABLED=true
FOUNDATION_RATE_LIMITS=configs/auth/rate_limits.json
FOUNDATION_RATE_LIMIT_STATE=outputs/auth/rate_limit_state.json
```

Use `configs/auth/rate_limits.example.json` as a template.

Example config:

```json
{
  "default": {"enabled": true, "limit": 120, "window_seconds": 60},
  "by_scope": {
    "model:invoke": {"limit": 30, "window_seconds": 60}
  },
  "by_key_id": {
    "dev-admin": {"limit": 600, "window_seconds": 60}
  }
}
```

Backend selection:

```text
FOUNDATION_QUOTA_BACKEND=file|sqlite
FOUNDATION_QUOTA_DB=outputs/auth/quota.sqlite
```

Compatibility aliases:

```text
FOUNDATION_RATE_LIMIT_BACKEND=file|sqlite
FOUNDATION_RATE_LIMIT_DB=outputs/auth/quota.sqlite
```

Default backend is `file`, preserving the previous `FOUNDATION_RATE_LIMIT_STATE` JSON behavior. SQLite backend stores counters in `rate_limit_buckets` with one row per API key/scope/workspace bucket.

When enabled, responses include rate limit headers:

```text
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
Retry-After
```

The failure envelope includes `error.details.quota_store` so operators can see whether the file or SQLite backend made the rate limit decision.

## Public endpoints

These endpoints do not require API keys even when auth is enabled:

- `/health`
- `/v1/health`
- `/docs`
- `/openapi.json`

## Current limitations

- This is API key based auth, not full OAuth/OIDC.
- Key store is file based.
- File rate limit backend is process-local and has no cross-process lock.
- SQLite rate limit backend is local-node SQLite, not a distributed rate limit service.
- No key rotation workflow yet.
- No request body workspace binding yet.
- No per-provider or per-model quota enforcement yet.

## Next steps

- Add API key generation and rotation helper.
- Add request-body workspace binding.
- Add Postgres/distributed rate limiting backend.
- Add provider/model quota checks.
