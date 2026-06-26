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

- Static OpenAPI contract still needs to be synchronized with the new helper routes.
- Provider execution is available in `/v1/chat`, but Agent runtime does not yet execute providers.
- Agent skill loop is not implemented yet.
- No streaming API yet.
- No authentication layer yet.
- No database-backed memory or run store yet.

## Next steps

- Integrate provider factory into `agent/runtime.py`.
- Add Agent skill loop.
- Update static OpenAPI contract with all runtime helper routes.
- Add authentication, workspace and API key scopes.
- Add streaming events.
