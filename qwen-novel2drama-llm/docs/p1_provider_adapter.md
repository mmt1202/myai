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
- `scripts/provider_smoke_test.py`
- `requirements/provider-smoke.txt`
- `tests/test_provider_adapter_contract.py`
- `tests/test_provider_factory.py`
- `tests/test_local_text_provider.py`
- `tests/test_provider_continuation.py`
- `tests/test_provider_smoke_config.py`

## Base provider contract

`providers/base.py` defines the provider error, response envelope, usage normalization, stream event and continuation capability contracts.

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

## Provider-native continuation adapter

`providers/realtime_base.py` defines the provider-native continuation adapter boundary:

- `ProviderNativeContinuationAdapter`
- `TestDoubleContinuationAdapter`
- `adapter_for_protocol(protocol)`

The test-double protocols are:

```text
provider_native_test
openai_realtime_test
openai_responses_test
```

These protocols do not call a real provider. They prove that provider-native continuation chunks can pass through the provider factory and Agent stream bridge without falling back to a next provider request.

Reserved real protocol names:

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
- normalize provider usage into foundation usage fields
- return standard response envelopes
- normalize HTTP and connection errors
- send native `stream=true` chat completions requests
- parse provider SSE `data: {...}` lines
- emit streamed text and streamed tool-call chunks
- reconstruct streamed tool calls by `index`
- route explicitly configured provider-native test continuation protocols to `providers/realtime_base.py`

## Gated provider smoke runner

`providers` can be checked against a real OpenAI-compatible endpoint through:

```text
scripts/provider_smoke_test.py
requirements/provider-smoke.txt
```

Default behavior is safe:

- not enabled by default
- missing config returns `skipped`
- `--dry-run` validates config/request shape without a provider call
- public output reports only whether a credential variable is configured, never its value

Configuration env:

```text
FOUNDATION_PROVIDER_SMOKE_ENABLED
FOUNDATION_PROVIDER_SMOKE_BASE_URL
FOUNDATION_PROVIDER_SMOKE_MODEL
FOUNDATION_PROVIDER_SMOKE_CREDENTIAL_ENV
FOUNDATION_PROVIDER_SMOKE_TIMEOUT
```

Commands:

```bash
python scripts/provider_smoke_test.py --dry-run --json
python scripts/provider_smoke_test.py --json
```

CI profile:

```bash
python scripts/ci_profiles.py --profile provider-smoke
python -m unittest tests.test_provider_smoke_config
```

## Local text provider

`providers/local_text.py` adapts the existing local `inference/model_utils.py` runtime to the provider contract.

It supports local dry-run, local model resolution, cache/concurrency controls, local text generation, local streaming and standard response envelopes.

## Current limitations

- Provider-native continuation v1 includes a test-double adapter and explicit OpenAI-compatible routing for configured test protocols.
- Real OpenAI Realtime/Responses same-session continuation is still not implemented.
- Provider smoke runner is gated and optional; it is not part of default core CI.
- Workflow creation for provider smoke was blocked by the connector safety layer and is not yet present.
- Provider-specific realtime session management still needs dedicated adapters.
