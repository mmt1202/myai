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
- `.github/workflows/foundation-provider-smoke.yml`
- `tests/test_provider_adapter_contract.py`
- `tests/test_provider_factory.py`
- `tests/test_local_text_provider.py`
- `tests/test_provider_continuation.py`
- `tests/test_provider_smoke_config.py`

## Provider-native continuation adapter

`providers/realtime_base.py` defines the provider-native continuation adapter boundary and concrete adapters:

- `ProviderNativeContinuationAdapter`
- `TestDoubleContinuationAdapter`
- `OpenAIResponsesContinuationAdapter`
- `OpenAIRealtimeSessionContinuationAdapter`
- `adapter_for_protocol(protocol)`

Protocols:

```text
provider_native_test
openai_realtime_test
openai_responses_test
openai_responses
openai_realtime
```

`openai_responses` posts tool results back through the Responses API by appending a `function_call_output` item to the input list and calling `/responses`.

`openai_realtime` requires an existing realtime session object in `stream_context["realtime_session"]`. The adapter sends a `conversation.item.create` function-call-output event and then a `response.create` event before reading response events from the provided session.

## OpenAI-compatible provider

`providers/openai_compatible.py` supports OpenAI-compatible chat completions and routes configured provider-native continuation protocols to `providers/realtime_base.py`.

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
- continue via `openai_responses` or a caller-supplied `openai_realtime` session when configured

## Gated provider smoke runner

`providers` can be checked against a real OpenAI-compatible endpoint through:

```text
scripts/provider_smoke_test.py
requirements/provider-smoke.txt
.github/workflows/foundation-provider-smoke.yml
```

Default behavior is safe:

- not enabled by default
- missing config returns `skipped`
- `--dry-run` validates config/request shape without a provider call
- public output reports only whether a credential variable is configured, never its value
- workflow is manual and only runs config tests plus dry-run by default

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

- `openai_responses` is request-based continuation, not a WebSocket session.
- `openai_realtime` adapter requires the caller to provide an already-open realtime session object; this project still does not own browser/WebRTC connection setup.
- Provider smoke runner is gated and optional; it is not part of default core CI.
- Provider-specific production session lifecycle management still needs deployment hardening.
