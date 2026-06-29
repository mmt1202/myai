# P1 Provider Adapter

Provider adapters normalize model provider calls for the foundation layer.

Applications should not call model providers directly. They should call the foundation API, and the foundation layer should route to provider adapters.

Implemented files:

- `providers/__init__.py`
- `providers/base.py`
- `providers/realtime_base.py`
- `providers/openai_compatible.py`
- `providers/local_text.py`
- `providers/factory.py`
- `tests/test_provider_adapter_contract.py`
- `tests/test_provider_factory.py`
- `tests/test_local_text_provider.py`
- `tests/test_provider_continuation.py`

## Base provider contract

`providers/base.py` defines:

- `ProviderError`
- `text_from_content_blocks`
- `output_text_block`
- `response_envelope`
- `normalize_usage`
- `provider_stream_event`
- `continuation_capability`
- `chunk_text`
- `BaseProvider.generate`
- `BaseProvider.stream_generate`
- `BaseProvider.continuation_capability`
- `BaseProvider.supports_bidirectional_tool_continuation`
- `BaseProvider.continue_stream_with_tool_result`

The base contract standardizes:

- content block normalization
- response envelope shape
- provider usage normalization
- provider error normalization
- provider stream chunk shape
- provider continuation capability reporting
- provider-native same-stream continuation hook
- capability checks
- modality checks

## Provider stream events

Supported event types:

- `provider_stream_started`
- `provider_stream_delta`
- `provider_stream_tool_call_delta`
- `provider_stream_tool_result`
- `provider_stream_continuation_started`
- `provider_stream_continuation_delta`
- `provider_stream_continuation_completed`
- `provider_stream_continuation_unsupported`
- `provider_stream_continuation_failed`
- `provider_stream_completed`
- `provider_stream_failed`

The completed event can include final `output`, `usage` and reconstructed `tool_calls`.

## Same-stream tool-result continuation contract

Providers can report whether they support provider-native bidirectional continuation:

```python
provider.continuation_capability()
provider.supports_bidirectional_tool_continuation()
```

Default provider behavior is unsupported:

```text
protocol = unsupported
mode = fallback_next_provider_request
```

The provider hook is:

```python
provider.continue_stream_with_tool_result(request, tool_call, tool_result, stream_context)
```

Unsupported providers emit `provider_stream_continuation_unsupported` through the Agent stream bridge and fall back to the normal next-provider-request tool loop.

Model instances can declare native support under runtime config:

```json
{
  "runtime_config": {
    "bidirectional_tool_continuation": {
      "supported": true,
      "protocol": "provider_native_test",
      "mode": "provider_native"
    }
  }
}
```

## Provider-native continuation adapter

`providers/realtime_base.py` defines the provider-native continuation adapter boundary:

- `ProviderNativeContinuationAdapter`
- `TestDoubleContinuationAdapter`
- `adapter_for_protocol(protocol)`
- `provider_stream_continuation_started`
- `provider_stream_continuation_delta`
- `provider_stream_continuation_completed`

The test-double protocols are:

```text
provider_native_test
openai_realtime_test
openai_responses_test
```

These protocols do not call a real provider. They prove that a provider-native continuation adapter can emit continuation chunks through the provider factory and Agent stream bridge without falling back to a next provider request.

Known real protocol names are reserved:

```text
openai_realtime
openai_responses
```

They require dedicated provider-specific sessions before being marked operational.

## OpenAI-compatible provider

`providers/openai_compatible.py` supports OpenAI-compatible chat completions.

It can:

- build chat messages from content blocks
- build `/chat/completions` payloads
- pass tools and tool choice when provided
- run in dry-run mode without network calls
- support `dry_run_provider` as a provider-level dry-run alias
- normalize provider usage into foundation usage fields
- return standard response envelopes
- normalize HTTP and connection errors
- send native `stream=true` chat completions requests
- parse provider SSE `data: {...}` lines
- stop on `data: [DONE]`
- convert remote text deltas to `ProviderStreamEvent` chunks
- emit `provider_stream_tool_call_delta` for remote `delta.tool_calls` chunks
- reconstruct streamed tool calls by `index`
- append fragmented `function.name` and `function.arguments`
- decode complete JSON arguments into `arguments_json` when possible
- include final streamed text, usage and reconstructed tool calls in `provider_stream_completed`
- route explicitly configured provider-native test continuation protocols to `providers/realtime_base.py`

Native OpenAI-compatible streaming through CLI:

```bash
MODEL_API_KEY=your_key python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url https://provider.example/v1 \
  --stream
```

Tool call streaming behavior:

```text
delta.tool_calls[index].id                    -> tool_calls[index].id
delta.tool_calls[index].type                  -> tool_calls[index].type
delta.tool_calls[index].function.name         -> appended function.name
delta.tool_calls[index].function.arguments    -> appended function.arguments
```

The provider adapter reconstructs tool calls. `/v1/chat` does not execute them; Agent can bridge them into the model tool loop with `stream_provider_tool_calls`. Agent can also execute complete partial streamed tool calls early with `incremental_stream_tool_execution` when the partial includes a name and JSON-decodable arguments.

## Local text provider

`providers/local_text.py` adapts the existing local `inference/model_utils.py` runtime to the provider contract.

It can:

- build prompts from foundation content blocks
- resolve model path from request, environment or model instance runtime config
- run dry-run without loading model weights
- load local transformers model through `model_utils.load_model`
- cache loaded local model runtimes in process
- protect cache load with a process-local load lock
- serialize generation per cached model by default
- expose cache stats through provider health and dry-run output
- generate text through `model_utils.generate_text`
- stream local text through `model_utils.generate_text_stream`
- fall back to chunked streaming when native streamer is unavailable
- return standard response envelopes
- estimate usage for local runs

## Current limitations

- Provider-native continuation v1 includes a test-double adapter and explicit OpenAI-compatible routing for configured test protocols.
- Real OpenAI Realtime/Responses same-session tool-result injection is still not implemented.
- Same-stream continuation can still fall back to the next-provider-request loop when unsupported.
- Provider-specific realtime session management still needs dedicated adapters.
