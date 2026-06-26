# P1 API Server Integration

The FastAPI server now exposes foundation services through `/v1/*` routes while preserving the old `/generate` local model endpoint.

Implemented files:

- `inference/api_server.py`
- `tests/test_api_server_foundation.py`

## Start server

Start with local model loading:

```bash
python inference/api_server.py --model-path /path/to/model
```

Start only foundation APIs without loading local model weights:

```bash
python inference/api_server.py --skip-model-load
```

The second mode is useful for routing, token/cost, memory, rules, skills, MCP and agent API testing.

## Auth mode

Auth is disabled by default for local development.

Enable API key enforcement:

```bash
FOUNDATION_AUTH_REQUIRED=true \
FOUNDATION_API_KEYS=configs/auth/api_keys.json \
python inference/api_server.py --skip-model-load
```

Use headers:

```text
X-API-Key: your_api_key
X-Workspace-Id: your_workspace_id
```

`/health`, `/v1/health`, `/docs` and `/openapi.json` remain public.

## Legacy endpoint

The old endpoint remains:

- `POST /generate`

It still requires a loaded local model.

## Foundation endpoints

New endpoints:

- `GET /v1/health`
- `POST /v1/chat`
- `POST /v1/reason`
- `POST /v1/multimodal/analyze`
- `POST /v1/token/count`
- `POST /v1/cost/estimate`
- `POST /v1/route`
- `POST /v1/memory/search`
- `POST /v1/memory/write`
- `POST /v1/rules/evaluate`
- `GET /v1/skills/list`
- `POST /v1/skills/call`
- `GET /v1/mcp/tools`
- `POST /v1/mcp/call`
- `POST /v1/agent/run`

## Chat and provider execution

`/v1/chat`, `/v1/reason` and `/v1/multimodal/analyze` route the request first.

By default, provider execution is skipped and the API returns route, usage and cost estimates.

To call a provider adapter, pass:

```json
{
  "execute_provider": true,
  "base_url": "https://provider.example/v1",
  "api_key_env": "MODEL_API_KEY"
}
```

This keeps routing and cost preflight safe by default.

## Local provider execution

The local model instance `local.qwen2_5_1_5b_instruct` now uses `providers/local_text.py` through the provider factory.

Local provider dry-run does not load model weights:

```json
{
  "route_mode": "local_first",
  "execute_provider": true,
  "dry_run_provider": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Real local execution needs a model path:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python inference/api_server.py --skip-model-load
```

or a request field:

```json
{
  "execute_provider": true,
  "model_path": "/path/to/model",
  "input": [{"type": "text", "text": "hello"}]
}
```

## Agent provider execution and skill loop

`/v1/agent/run` supports provider execution and registered skill calls through `agent/runtime.py`.

Provider preflight only:

```json
{
  "task": "summarize this",
  "route_mode": "smart",
  "approval_policy": "never"
}
```

Provider dry-run execution:

```json
{
  "task": "summarize this",
  "route_mode": "smart",
  "approval_policy": "never",
  "execute_provider": true,
  "dry_run_provider": true,
  "base_url": "http://localhost:8000/v1"
}
```

Skill loop execution:

```json
{
  "task": "count tokens before running",
  "route_mode": "balanced",
  "approval_policy": "never",
  "skill_calls": [
    {
      "name": "foundation.token_count",
      "arguments": {
        "request": {"input": [{"type": "text", "text": "hello"}]},
        "expected_output_tokens": 10
      }
    }
  ]
}
```

Skill permission flags can be supplied per skill call or as request-level defaults:

- `allow_skill_provider`
- `allow_skill_write`
- `approve_skills`

The agent writes run artifacts under:

```text
outputs/agent_runtime/api/<request_id-or-latest>/
```

Artifacts can include:

- `agent_run_report.json`
- `provider_response.json`
- `skill_results.json`
- `usage_ledger.jsonl`

## Memory

The API uses:

```text
outputs/memory/memory.jsonl
```

for the default JSONL memory store.

## MCP

`/v1/mcp/tools` exposes skills as MCP-style tools.

`/v1/mcp/call` calls the MCP adapter with optional permission flags:

- `allow_provider`
- `allow_write`
- `approved`

## Current limitations

- Agent skill loop is synchronous and request-driven, not model-decided multi-turn tool calling yet.
- Local provider is text-only and loads weights in-process.
- No streaming API yet.
- Auth is API-key based, not full OAuth/OIDC.
- No rate limiting yet.
- No database-backed memory or run store yet.

## Next steps

- Add model-decided Agent tool loop.
- Add local provider concurrency controls.
- Add auth audit log and rate limiting.
- Add workspace-level budget and quota checks.
- Add streaming events.
