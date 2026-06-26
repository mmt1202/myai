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
7. decide final status
8. write `agent_run_report.json`

Possible final states:

- `completed`
- `waiting_approval`
- `failed`

## CLI

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo
```

Example request:

```json
{
  "task": "summarize this request",
  "route_mode": "balanced",
  "approval_policy": "on_cost",
  "input": [
    {"type": "text", "text": "hello"}
  ],
  "privacy": {"local_only": true}
}
```

## Current limitations

- Does not call provider APIs yet.
- Does not execute tool loops yet.
- Does not resume from existing run files yet.
- Does not persist to a database yet.
- Approval resolution is not implemented yet.

## Next steps

- Add provider adapter base.
- Add provider execution step.
- Add tool execution step.
- Add resume/cancel/retry CLI commands.
- Add API server integration for `/v1/agent/run`.
