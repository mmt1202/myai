# P1 OpenAPI Contract Check

This tool keeps the FastAPI runtime and static OpenAPI contract aligned.

Implemented files:

- `scripts/check_openapi_contract.py`
- `tests/test_openapi_contract_check.py`

## Checks

The checker compares:

- `/v1/*` routes declared in `inference/api_server.py`
- `/v1/*` paths declared in `openapi/foundation_api.openapi.yaml`

It also checks that important OpenAPI sections and fields are present, including:

- `ApiKeyAuth`
- `FoundationRequest`
- `FoundationResponse`
- `AgentRunRequest`
- `AgentSkillCall`
- `AgentEvent`
- `AgentEventsResponse`
- provider execution fields
- request-driven skill loop fields
- model tool loop fields
- Agent event stream fields such as `disable_events` and `text/event-stream`

Current required runtime endpoints include `GET /v1/agent/events`.

## Run

From project root:

```bash
python scripts/check_openapi_contract.py
```

JSON report:

```bash
python scripts/check_openapi_contract.py --json
```

Expected success output:

```text
openapi_contract_check=ok
```

## Purpose

The foundation API now includes router, token/cost, memory, rules, skills, MCP, API key mode, provider execution, Agent tool loop controls and live Agent event reads.

This check helps keep runtime routes and the static OpenAPI file consistent as the API changes.

## Current limitations

- The script uses lightweight static parsing.
- It checks paths and important tokens, not full OpenAPI semantic validity.
- It only compares `/v1/*` runtime endpoints.

## Next steps

- Add this script to CI.
- Add full OpenAPI schema validation later.
- Add generated client smoke tests.
- Add endpoint-level scope consistency checks later.
