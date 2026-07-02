# OpenAI Responses Provider

This document records the repository-level OpenAI Responses adapter contract.

## Implemented files

```text
providers/openai_responses.py
providers/factory.py
scripts/openai_responses_smoke.py
tests/test_openai_responses_provider.py
tests/test_openai_responses_smoke.py
```

## Runtime selection

The model registry uses:

```text
runtime = openai_responses
provider = openai
```

When `providers.factory.build_provider()` sees `runtime=openai_responses`, it returns `OpenAIResponsesProvider`.

## Environment

```text
OPENAI_MODEL=<configured outside git>
OPENAI_API_KEY=<configured outside git>
OPENAI_BASE_URL=https://api.openai.com/v1
```

`MODEL_API_KEY` is treated as a generic fallback name. For the OpenAI Responses adapter, the registry-specific key env is preferred unless the caller explicitly passes a custom key env.

## Payload mapping

Foundation request blocks are mapped to Responses input blocks:

```text
text / subtitle / reasoning_hint / tool_result / metadata -> input_text
image -> input_image
file / url -> input_file
audio / video -> text placeholder in v1
```

Supported request fields:

```text
model
input
system
developer
instructions
max_output_tokens
temperature
tools
tool_choice
response_format
metadata
store
stream
stream_options
```

## Native streaming

The adapter now supports provider-native Responses streaming:

```text
request stream=true -> provider payload stream=true
SSE event/data parser -> iter_sse_json()
response.output_text.delta-style events -> provider_stream_delta
response.completed-style events -> provider_stream_completed
response.failed/error-style events -> ProviderError
```

The stream implementation intentionally keeps raw provider event metadata in each emitted event so future Responses event variants remain debuggable.

## Dry run

Every CI-safe provider path should use:

```json
{
  "dry_run": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Dry run returns the provider payload and does not call the network. Dry-run streaming also works and emits started/delta/completed events.

## Smoke script

Dry run smoke:

```bash
python scripts/openai_responses_smoke.py
```

Dry run stream smoke:

```bash
python scripts/openai_responses_smoke.py --stream
```

Live smoke, only after real env values are configured:

```bash
python scripts/openai_responses_smoke.py --live
python scripts/openai_responses_smoke.py --live --stream
```

Live smoke returns `skipped` when no API key is configured and `failed` only when a configured live call fails.

## Boundaries

- Adapter implemented does not mean a real OpenAI account, model name, billing, org policy, or API key has been configured.
- Native streaming is implemented at the SSE event parser level, but live behavior still requires a configured API key, model name and model access.
- Audio/video blocks are not uploaded as native Responses media in v1; they are represented as text placeholders until a dedicated file upload/media path is added.
