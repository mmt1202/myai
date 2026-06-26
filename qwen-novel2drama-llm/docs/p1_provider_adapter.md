# P1 Provider Adapter

Provider adapters normalize model provider calls for the foundation layer.

Applications should not call external model providers directly. They should call the foundation API, and the foundation layer should route to provider adapters.

Implemented files:

- `providers/__init__.py`
- `providers/base.py`
- `providers/openai_compatible.py`
- `tests/test_provider_adapter_contract.py`

## Base provider contract

`providers/base.py` defines:

- `ProviderError`
- `text_from_content_blocks`
- `output_text_block`
- `response_envelope`
- `normalize_usage`
- `BaseProvider`

The base contract standardizes:

- content block normalization
- response envelope shape
- provider usage normalization
- provider error normalization
- capability checks
- modality checks

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

## Real provider call

```bash
MODEL_API_KEY=your_key python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url https://provider.example/v1
```

## Current limitations

- Text-first chat completions adapter only.
- Image/video/audio generation adapters are not implemented yet.
- Streaming is not implemented yet.
- Provider-specific tokenizer reconciliation is not implemented yet.
- Provider health probing is basic.

## Next steps

- Integrate provider adapter into `agent/runtime.py`.
- Add local provider adapter for the existing text runtime.
- Add provider registry and factory.
- Add streaming support.
- Add image/video/audio provider adapter interfaces.
- Add actual usage ledger reconciliation after provider calls.
