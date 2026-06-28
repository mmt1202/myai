# P1 Agent Runtime

The foundation agent runtime is a generic task orchestration layer.

It is not a Claude Code or Codex replacement. It is the foundation runtime that later products can call when they need structured task execution.

Implemented files:

- `configs/schemas/agent_run_schema.json`
- `agent/__init__.py`
- `agent/runtime.py`
- `agent/events.py`
- `agent/tool_loop.py`
- `agent/lifecycle.py`
- `tests/test_agent_runtime.py`
- `tests/test_agent_events.py`
- `tests/test_agent_tool_loop.py`
- `tests/test_agent_lifecycle.py`

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

1. persist the original request to `agent_request.json`
2. create run
3. write `run_created` event
4. transition to running
5. check cancellation at key checkpoints
6. build foundation request
7. route model
8. estimate usage and cost through router output
9. evaluate rules
10. apply approval gate when needed
11. optionally execute request-defined skills
12. optionally execute provider through provider factory
13. optionally execute model-decided tool calls returned by the provider
14. optionally collect provider stream chunks and bridge reconstructed tool calls into the model tool loop
15. optionally execute complete streamed tool calls as soon as their name and JSON arguments are available
16. record estimated or actual usage in a run-local usage ledger
17. write `events.jsonl`
18. write `agent_run_report.json`

Possible final states:

- `completed`
- `waiting_approval`
- `failed`
- `cancelled`

## Agent event stream

The runtime writes a JSONL event stream for every run by default:

```text
outputs/agent_runtime/<run>/events.jsonl
```

The API server writes Agent runs under:

```text
outputs/agent_runtime/api/<request_id-or-run_id-or-latest>/
```

The final run report includes:

- `artifacts.request`
- `artifacts.events`
- `event_summary`

Common event types:

- `run_created`
- `run_started`
- `route_started`
- `route_completed`
- `route_failed`
- `rules_started`
- `rules_completed`
- `run_waiting_approval`
- `skill_loop_started`
- `skill_call_started`
- `skill_call_completed`
- `skill_call_failed`
- `skill_loop_completed`
- `skill_loop_failed`
- `provider_started`
- `provider_completed`
- `provider_failed`
- `provider_skipped`
- `model_tool_loop_started`
- `model_tool_loop_completed`
- `model_tool_loop_failed`
- `run_completed`
- `run_failed`
- `run_cancelled`

Read events from CLI:

```bash
python agent/events.py --events outputs/agent_runtime/demo/events.jsonl
```

Read summary from CLI:

```bash
python agent/events.py --events outputs/agent_runtime/demo/events.jsonl --summary
```

Disable event writing for a run:

```json
{
  "disable_events": true
}
```

or CLI:

```bash
python agent/runtime.py --request examples/agent_request.json --disable-events
```

## Live Agent events API

`GET /v1/agent/events` can read existing events as JSON or stream new events as Server-Sent Events.

JSON mode:

```text
GET /v1/agent/events?run_id=demo
```

SSE mode:

```text
GET /v1/agent/events?run_id=demo&stream=true
```

Supported query parameters:

- `run_id`
- `stream`
- `since_event_id`
- `limit`
- `poll_interval`
- `max_seconds`

SSE frames use:

```text
id: <event_id>
event: <event_type>
data: <full event JSON>
```

The stream stops when it emits a terminal event or reaches `max_seconds`.

## Agent lifecycle controls

`agent/lifecycle.py` provides file-backed lifecycle operations:

- `status`
- `cancel`
- `retry`
- `resume`

Status:

```bash
python agent/lifecycle.py \
  --output-root outputs/agent_runtime/api \
  status \
  --run-id demo
```

Cancel:

```bash
python agent/lifecycle.py \
  --output-root outputs/agent_runtime/api \
  cancel \
  --run-id demo \
  --reason user_requested
```

Cancel writes:

```text
cancel_requested.json
```

The runtime checks this file at key checkpoints and transitions to `cancelled` with a `run_cancelled` event when it sees the marker. This is cooperative cancellation, not hard provider process interruption.

Retry:

```bash
python agent/lifecycle.py \
  --project-root . \
  --output-root outputs/agent_runtime/api \
  retry \
  --run-id demo \
  --new-run-id demo_retry
```

Resume:

```bash
python agent/lifecycle.py \
  --project-root . \
  --output-root outputs/agent_runtime/api \
  resume \
  --run-id demo \
  --new-run-id demo_resume \
  --overrides '{"skill_calls": []}'
```

Retry/resume load `agent_request.json`, merge optional overrides, assign a new run id and call the normal runtime again. The child run records `retry_of` or `resume_of` and `parent_run_id`.

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
- `events.jsonl`
- `agent_run_report.json`

A denied or failing skill fails the run unless `continue_on_error` is true for that skill call.

## Model-decided tool loop

The runtime can inspect provider responses for OpenAI-style `tool_calls`.

Enable it with:

```json
{
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "max_tool_rounds": 3
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
- `events.jsonl`
- `agent_run_report.json`

## Provider stream tool-call bridge

`stream_provider_tool_calls` makes the provider step use provider streaming when the model tool loop is enabled.

```json
{
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "stream_provider_tool_calls": true,
  "stream_include_usage": true
}
```

With this enabled, the runtime:

1. calls the selected provider through `stream_generate_with_registry`
2. writes raw provider stream chunks to `provider_stream_chunks.jsonl`
3. converts the final `provider_stream_completed` chunk into a standard provider response
4. reads `output.tool_calls` from that response
5. executes matching foundation skills through the existing model tool loop
6. optionally streams follow-up provider rounds and writes `model_tool_loop_stream_round_<n>.jsonl`

## Incremental stream tool execution

`incremental_stream_tool_execution` can execute a streamed tool call before the provider stream has completed, once the partial tool call has both a tool name and JSON-decodable arguments.

```json
{
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "stream_provider_tool_calls": true,
  "incremental_stream_tool_execution": true
}
```

With this enabled, the runtime:

1. listens for `provider_stream_tool_call_delta` chunks
2. reads `metadata.tool_call_partial`
3. waits until `function.name` and complete JSON `function.arguments` are available
4. executes the matching foundation skill immediately
5. records the result in `incremental_tool_results.json`
6. reuses the pre-executed result in the final model tool loop to avoid duplicate tool calls

For streamed follow-up rounds, it writes:

```text
model_tool_loop_incremental_round_<n>.json
```

This is not yet same-stream tool-result injection. The provider stream is still read to completion before the next provider request is made.

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

- `agent_request.json`
- `provider_response.json`
- `usage_ledger.jsonl`
- `events.jsonl`
- `agent_run_report.json`

When `stream_provider_tool_calls` is enabled, it also writes:

- `provider_stream_chunks.jsonl`
- `model_tool_loop_stream_round_<n>.jsonl` for streamed follow-up rounds

When `incremental_stream_tool_execution` is enabled, it also writes:

- `incremental_tool_results.json`
- `model_tool_loop_incremental_round_<n>.json` for streamed follow-up rounds

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

Streamed provider tool-call bridge:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo \
  --execute-provider \
  --enable-model-tool-loop \
  --stream-provider-tool-calls \
  --stream-include-usage
```

Incremental stream tool execution:

```bash
python agent/runtime.py \
  --request examples/agent_request.json \
  --output-dir outputs/agent_runtime/demo \
  --execute-provider \
  --enable-model-tool-loop \
  --stream-provider-tool-calls \
  --incremental-stream-tool-execution
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

- Cancel is cooperative and checkpoint-based; it does not forcibly terminate an in-flight provider call.
- Retry/resume are replay-based and create a child run; they do not continue from an arbitrary internal Python stack frame.
- Resume from completed runs is blocked by default unless explicitly allowed.
- Incremental execution requires complete JSON arguments; partial or malformed arguments are ignored until they become complete.
- Incremental execution does not inject tool results back into the same open provider stream.
- Tool execution is still synchronous.
- Stream chunks are stored as JSONL files, not a distributed event log.
- Lifecycle state is file-backed, not a distributed run database.
- Approval is coarse-grained and not yet a full human-in-the-loop workflow.
