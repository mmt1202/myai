# P1 Provider Adapter

Provider adapters normalize model provider calls for the foundation layer.

Applications should not call model providers directly. They should call the foundation API, and the foundation layer should route to provider adapters.

Implemented files:

- `providers/__init__.py`
- `providers/base.py`
- `providers/openai_compatible.py`
- `providers/local_text.py`
- `providers/factory.py`
- `tests/test_provider_adapter_contract.py`
- `tests/test_provider_factory.py`
- `tests/test_local_text_provider.py`

## Base provider contract

`providers/base.py` defines:

- `ProviderError`
- `text_from_content_blocks`
- `output_text_block`
- `response_envelope`
- `normalize_usage`
- `provider_stream_event`
- `chunk_text`
- `BaseProvider.generate`
- `BaseProvider.stream_generate`

The base contract standardizes:

- content block normalization
- response envelope shape
- provider usage normalization
- provider error normalization
- provider stream chunk shape
- capability checks
- modality checks

## Provider stream events

Provider streams emit standard chunks:

```json
{
  "chunk_id": "chunk_...",
  "event_type": "provider_stream_delta",
  "delta": "partial text",
  "done": false
}
```

Supported event types:

- `provider_stream_started`
- `provider_stream_delta`
- `provider_stream_tool_call_delta`
- `provider_stream_completed`
- `provider_stream_failed`

The completed event can include final `output`, `usage` and reconstructed `tool_calls`.

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

Native OpenAI-compatible streaming through CLI:

```bash
MODEL_API_KEY=your_key python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url https://provider.example/v1 \
  --stream
```

Optional stream usage request:

```json
{
  "stream": true,
  "stream_include_usage": true
}
```

This sets:

```json
{
  "stream_options": {"include_usage": true}
}
```

when building the OpenAI-compatible payload.

Tool call streaming behavior:

```text
delta.tool_calls[index].id              -> tool_calls[index].id
delta.tool_calls[index].type            -> tool_calls[index].type
delta.tool_calls[index].function.name   -> appended function.name
delta.tool_calls[index].function.arguments -> appended function.arguments
```

The final completed event can include:

```json
{
  "output": {
    "tool_calls": [
      {
        "id": "call_...",
        "type": "function",
        "function": {
          "name": "foundation.token_count",
          "arguments": "{\"request\":{\"input\":[]}}"
        },
        "arguments_json": {"request": {"input": []}}
      }
    ]
  }
}
```

The provider adapter only reconstructs tool calls; it does not execute them.

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

Local provider config can come from request fields:

```json
{
  "model_path": "/path/to/model",
  "adapter_path": "/path/to/lora",
  "system_prompt_file": "prompts/system_prompt.txt",
  "use_cache": true,
  "serialize_generation": true,
  "stream": true,
  "stream_chunk_chars": 128
}
```

or environment variables:

```text
FOUNDATION_LOCAL_MODEL_PATH
FOUNDATION_LOCAL_ADAPTER_PATH
FOUNDATION_LOCAL_SYSTEM_PROMPT
```

Runtime cache helpers:

- `cache_stats()`
- `clear_model_cache()`
- `local_cache_key()`

CLI cache helpers:

```bash
python providers/local_text.py --request examples/provider_request.json --cache-stats
python providers/local_text.py --request examples/provider_request.json --clear-cache --cache-stats
```

Streaming local provider through CLI:

```bash
python providers/local_text.py \
  --request examples/provider_request.json \
  --model-path /path/to/model \
  --stream
```

Dry-run local provider stream through factory:

```bash
python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id local.qwen2_5_1_5b_instruct \
  --stream
```

Real local execution requires `model_path` in the request or `FOUNDATION_LOCAL_MODEL_PATH`.

## Provider factory

`providers/factory.py` can:

- find a model instance by id or alias
- build a provider from model instance metadata
- call OpenAI-compatible providers
- call local transformers providers
- call a provider through `generate_with_registry`
- stream a provider through `stream_generate_with_registry`
- return standard response envelopes on provider errors

## Dry run

```bash
python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url http://localhost:8000/v1
```

Request field:

```json
{
  "dry_run": true,
  "request_id": "demo",
  "input": [{"type": "text", "text": "hello"}]
}
```

Provider-level dry-run alias:

```json
{
  "dry_run_provider": true
}
```

## Real provider call

OpenAI-compatible:

```bash
MODEL_API_KEY=your_key python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url https://provider.example/v1
```

OpenAI-compatible streaming:

```bash
MODEL_API_KEY=your_key python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id external.openai_compatible.smart \
  --base-url https://provider.example/v1 \
  --stream
```

Local transformers:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id local.qwen2_5_1_5b_instruct
```

Local transformers streaming:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id local.qwen2_5_1_5b_instruct \
  --stream
```

## Current limitations

- Local provider is text-only.
- Local provider loads model weights in-process.
- Local cache is process-local, not distributed.
- Generation serialization is per-process, not cluster-wide.
- Streamed tool-call reconstruction supports OpenAI-style function tool calls only.
- Reconstructed tool calls are not automatically executed by the provider adapter.
- Image/video/audio generation adapters are not implemented yet.
- Provider-specific tokenizer reconciliation is not implemented yet.
- Provider health probing is still basic.

## Next steps

- Bridge streamed provider tool calls into Agent tool loop execution.
- Add provider usage reconciliation after provider calls.
- Add local provider warmup endpoint.
- Add local provider memory-pressure eviction policy.
- Add image/video/audio provider adapter interfaces.
