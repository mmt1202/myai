# P1 Agent Runtime

The foundation Agent runtime is a generic task orchestration layer for structured task execution.

Implemented files:

- `configs/schemas/agent_run_schema.json`
- `agent/runtime.py`
- `agent/events.py`
- `agent/tool_loop.py`
- `agent/lifecycle.py`
- `inference/api_server.py`
- `tests/test_agent_runtime.py`
- `tests/test_agent_events.py`
- `tests/test_agent_tool_loop.py`
- `tests/test_agent_lifecycle.py`
- `tests/test_api_server_foundation.py`
- `tests/test_provider_continuation.py`

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
16. optionally emit tool-result and continuation fallback events for same-stream tool-result injection requests
17. record estimated or actual usage in a run-local usage ledger
18. write `events.jsonl`
19. write `agent_run_report.json`

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

`GET /v1/agent/events` can read existing events as JSON or stream new events as Server-Sent Events.

JSON mode:

```text
GET /v1/agent/events?run_id=demo
```

SSE mode:

```text
GET /v1/agent/events?run_id=demo&stream=true
```

## Agent lifecycle controls

`agent/lifecycle.py` provides file-backed lifecycle operations:

- `status`
- `cancel`
- `retry`
- `resume`

CLI examples:

```bash
python agent/lifecycle.py --output-root outputs/agent_runtime/api status --run-id demo
python agent/lifecycle.py --output-root outputs/agent_runtime/api cancel --run-id demo --reason user_requested
python agent/lifecycle.py --project-root . --output-root outputs/agent_runtime/api retry --run-id demo --new-run-id demo_retry
python agent/lifecycle.py --project-root . --output-root outputs/agent_runtime/api resume --run-id demo --new-run-id demo_resume --overrides '{"skill_calls": []}'
```

API endpoints:

```text
GET  /v1/agent/status?run_id=demo
POST /v1/agent/cancel
POST /v1/agent/retry
POST /v1/agent/resume
```

Cancel writes:

```text
cancel_requested.json
```

The runtime checks this file at key checkpoints and transitions to `cancelled` with a `run_cancelled` event when it sees the marker. This is cooperative cancellation, not hard provider process interruption.

Retry/resume load `agent_request.json`, merge optional overrides, assign a new run id and call the normal runtime again. The child run records `retry_of` or `resume_of` and `parent_run_id`.

## Request-driven skill loop

The runtime accepts `skill_calls` in the request.

Each skill call supports optional per-call permission flags:

- `allow_provider`
- `allow_write`
- `approved`
- `continue_on_error`

The run request also supports default skill permissions:

- `allow_skill_provider`
- `allow_skill_write`
- `approve_skills`

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

The runtime writes:

- `model_tool_loop.json`
- `model_tool_loop_usage_aggregation.json`
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

With this enabled, the runtime writes raw provider stream chunks to `provider_stream_chunks.jsonl`, converts the final `provider_stream_completed` chunk into a standard provider response, and executes reconstructed `output.tool_calls` through the existing model tool loop.

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

With this enabled, the runtime emits `provider_stream_tool_result`, writes `incremental_tool_results.json`, and reuses pre-executed results in the final model tool loop to avoid duplicate tool calls.

## Same-stream tool-result injection contract

`same_stream_tool_result_injection` requests provider-supported bidirectional continuation.

```json
{
  "execute_provider": true,
  "enable_model_tool_loop": true,
  "stream_provider_tool_calls": true,
  "incremental_stream_tool_execution": true,
  "same_stream_tool_result_injection": true
}
```

Stream events added for this contract:

- `provider_stream_tool_result`
- `provider_stream_continuation_unsupported`
- `provider_stream_continuation_failed`

Current default behavior:

1. execute the streamed tool call as soon as arguments are complete
2. emit `provider_stream_tool_result`
3. query provider continuation capability
4. if unsupported, emit `provider_stream_continuation_unsupported`
5. safely fall back to the existing next-provider-request tool loop

This is a protocol and safety fallback layer. It does not mean OpenAI-compatible/local providers already support true same-stream bidirectional continuation.

## Provider execution artifacts

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

When same-stream continuation is requested, `provider_stream_chunks.jsonl` may also include:

- `provider_stream_tool_result`
- `provider_stream_continuation_unsupported`
- `provider_stream_continuation_failed`

## Current limitations

- Agent lifecycle APIs are file-backed, not database-backed.
- Cancel is cooperative and checkpoint-based; it does not forcibly terminate an in-flight provider call.
- Retry/resume are replay-based and create a child run; they do not continue from an arbitrary internal Python stack frame.
- Same-stream tool-result injection is capability-gated; current providers default to unsupported.
- Unsupported providers fall back to next-provider-request continuation.
- No provider-native bidirectional streaming adapter is implemented yet.
- Tool execution is still synchronous.
- Stream chunks are stored as JSONL files, not a distributed event log.
- Lifecycle state is file-backed, not a distributed run database.
