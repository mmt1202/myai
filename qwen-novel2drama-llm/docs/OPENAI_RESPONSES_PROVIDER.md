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
```

## Dry run

Every CI-safe provider path should use:

```json
{
  "dry_run": true,
  "input": [{"type": "text", "text": "hello"}]
}
```

Dry run returns the provider payload and does not call the network.

## Smoke script

Dry run smoke:

```bash
python scripts/openai_responses_smoke.py
```

Live smoke, only after real env values are configured:

```bash
python scripts/openai_responses_smoke.py --live
```

Live smoke returns `skipped` when no API key is configured and `failed` only when a configured live call fails.

## Boundaries

- Adapter implemented does not mean a real OpenAI account, model name, billing, org policy, or API key has been configured.
- Streaming for Responses is not yet provider-native in this adapter; non-streaming generate and BaseProvider fallback stream are available.
- Audio/video blocks are not uploaded as native Responses media in v1; they are represented as text placeholders until a dedicated file upload/media path is added.
