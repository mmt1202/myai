# P1 Agent Runtime

The foundation agent runtime is a generic task orchestration layer.

It is not a Claude Code or Codex replacement. It is the foundation runtime that later products can call when they need structured task execution.

Implemented files:

- `configs/schemas/agent_run_schema.json`
- `agent/__init__.py`
- `agent/runtime.py`
- `tests/test_agent_runtime.py`

## Run states

Supported run and step states:

- `queued`
- `running`
- `waiting_tool`
- `waiting_approval`
- `completed`
- `failed`
- `cancelled`

The runtime enforces valid state transitions.

## Approval policies

Supported approval policies:

- `never`
- `on_write`
- `on_cost`
- `always`

Current runtime supports approval gates from rule decisions and cost thresholds.

## Runtime flow

`run_agent_once` currently performs:

1. create run
2. transition to running
3. build foundation request
4. route model
5. estimate usage and cost through router output
6. evaluate rules
7. apply approval gate when needed
8. optionally execute registered skills
9. optionally execute provider through provider factory
10. record estimated or actual usage in a run-local usage ledger
11. write `agent_run_report.json`

Possible final states:

- `completed`
- `waiting_approval`
- `failed`

## Skill loop

The runtime accepts `skill_calls` in the request.

Example:

```json
{
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

Each skill call supports optional per-call permission flags:

- `allow_provider`
- `allow_write`
- `approved`
- `continue_on_error`

The run request also supports default skill permissions:

- `allow_skill_provider`
- `allow_skill_write`
- `approve_skills`

When the skill loop runs, the runtime writes:

- `skill_results.json`
- `agent_run_report.json`

A denied or failing skill fails the run unless `continue_on_error` is true for that skill call.

## Provider execution

Provider execution is disabled by default.

Without `execute_provider`, the runtime stops after routing, policy checks and optional skill calls, records estimated usage, and marks the run completed with a `ready_for_provider` step.

To execute a provider:

```json
{
  "execute_provider": true,
  "dry_run_provider": true,
  "base_url": "http://localhost:8000/v1",
  "api_key_env": "MODEL_API_KEY"
}
```

`dry_run_provider` is useful for testing provider payload generation without network calls or local model loading.

Local provider execution is now supported through `providers/local_text.py`. Real local execution requires `model_path` in the request or `FOUNDATION_LOCAL_MODEL_PATH`.

When provider execution runs, the runtime writes:

- `provider_response.json`
- `usage_ledger.jsonl`
- `agent_run_report.json`

## CLI

Preflight only:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo
```

Provider dry-run:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo \
  --execute-provider \
  --dry-run-provider \
  --base-url http://localhost:8000/v1
```

Local provider real execution:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo \
  --execute-provider
```

Skill permissions can also be passed through CLI:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --allow-skill-write \
  --approve-skills
```

Example request:

```json
{
  "task": "summarize this request",
  "route_mode": "smart",
  "approval_policy": "never",
  "execute_provider": true,
  "dry_run_provider": true,
  "skill_calls": [
    {
      "name": "foundation.token_count",
      "arguments": {
        "request": {"input": [{"type": "text", "text": "hello"}]},
        "expected_output_tokens": 10
      }
    }
  ],
  "input": [
    {"type": "text", "text": "hello"}
  ]
}
```

## Current limitations

- Local provider is text-only and loads model weights in-process.
- Tool loop is synchronous and skill-call based; model-decided multi-turn tool calling is not implemented yet.
- Resume from existing run files is not implemented yet.
- Database persistence is not implemented yet.
- Approval resolution is not implemented yet.
- Streaming run events are not implemented yet.

## Next steps

- Add model-decided tool loop.
- Add local provider concurrency and cache controls.
- Add resume/cancel/retry CLI commands.
- Add streaming run events.
- Add provider usage reconciliation into the global usage ledger.
