# P1 Agent Runtime

The foundation agent runtime is a generic task orchestration layer.

It is not a Claude Code or Codex replacement. It is the foundation runtime that later products can call when they need structured task execution.

Implemented files:

- `configs/schemas/agent_run_schema.json`
- `agent/__init__.py`
- `agent/runtime.py`
- `agent/tool_loop.py`
- `tests/test_agent_runtime.py`
- `tests/test_agent_tool_loop.py`

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
8. optionally execute request-defined skills
9. optionally execute provider through provider factory
10. optionally execute model-decided tool calls returned by the provider
11. record estimated or actual usage in a run-local usage ledger
12. write `agent_run_report.json`

Possible final states:

- `completed`
- `waiting_approval`
- `failed`

## Request-driven skill loop

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

When the request-driven skill loop runs, the runtime writes:

- `skill_results.json`
- `agent_run_report.json`

A denied or failing skill fails the run unless `continue_on_error` is true for that skill call.

## Model-decided tool loop

The runtime can now inspect provider responses for OpenAI-style `tool_calls`.

Enable it with:

```json
{
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "max_tool_rounds": 3
}
```

Supported provider response shapes:

```json
{
  "output": {
    "raw_message": {
      "tool_calls": [
        {
          "id": "call_1",
          "type": "function",
          "function": {
            "name": "foundation.token_count",
            "arguments": "{\"request\":{\"input\":[{\"type\":\"text\",\"text\":\"hello\"}]}}"
          }
        }
      ]
    }
  }
}
```

For each model-decided tool call, the runtime:

1. normalizes the tool call
2. maps the tool name to a registered foundation skill
3. checks tool-loop permissions
4. executes the skill
5. appends a `tool_result` content block to the next provider request
6. calls the provider again
7. repeats until no more tool calls or `max_tool_rounds` is reached

Model tool-loop permissions:

- `allow_model_tool_provider`
- `allow_model_tool_write`
- `approve_model_tools`
- `fail_on_model_tool_error`

The runtime writes:

- `model_tool_loop.json`
- `agent_run_report.json`

## Provider execution

Provider execution is disabled by default.

Without `execute_provider`, the runtime stops after routing, policy checks and optional request-driven skill calls, records estimated usage, and marks the run completed with a `ready_for_provider` step.

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

Local provider execution is supported through `providers/local_text.py`. Real local execution requires `model_path` in the request or `FOUNDATION_LOCAL_MODEL_PATH`.

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

Model tool-loop mode:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo \
  --execute-provider \
  --enable-model-tool-loop \
  --max-tool-rounds 3
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

Model tool permissions can also be passed through CLI:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --execute-provider \
  --enable-model-tool-loop \
  --allow-model-tool-write \
  --approve-model-tools
```

## Current limitations

- Local provider is text-only and loads model weights in-process.
- Model-decided tool loop is synchronous.
- Tool names must map to registered foundation skill ids.
- No streaming tool-call events yet.
- Resume from existing run files is not implemented yet.
- Database persistence is not implemented yet.
- Approval resolution is not implemented yet.

## Next steps

- Add OpenAPI fields for model tool-loop controls.
- Add local provider concurrency and cache controls.
- Add resume/cancel/retry CLI commands.
- Add streaming run events.
- Add provider usage reconciliation into the global usage ledger.
