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

## Local text provider

`providers/local_text.py` adapts the existing local `inference/model_utils.py` runtime to the provider contract.

It can:

- build prompts from foundation content blocks
- resolve model path from request, environment or model instance runtime config
- run dry-run without loading model weights
- load local transformers model through `model_utils.load_model`
- generate text through `model_utils.generate_text`
- return standard response envelopes
- estimate usage for local runs

Local provider config can come from request fields:

```json
{
  "model_path": "/path/to/model",
  "adapter_path": "/path/to/lora",
  "system_prompt_file": "prompts/system_prompt.txt"
}
```

or environment variables:

```text
FOUNDATION_LOCAL_MODEL_PATH
FOUNDATION_LOCAL_ADAPTER_PATH
FOUNDATION_LOCAL_SYSTEM_PROMPT
```

Dry-run local provider through factory:

```bash
python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id local.qwen2_5_1_5b_instruct
```

Real local execution requires `model_path` in the request or `FOUNDATION_LOCAL_MODEL_PATH`.

## Provider factory

`providers/factory.py` can:

- find a model instance by id or alias
- build a provider from model instance metadata
- call OpenAI-compatible providers
- call local transformers providers
- call a provider through `generate_with_registry`
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

## Real provider call

OpenAI-compatible:

```bash
MODEL_API_KEY=your_key python providers/openai_compatible.py \
  --request examples/provider_request.json \
  --base-url https://provider.example/v1
```

Local transformers:

```bash
FOUNDATION_LOCAL_MODEL_PATH=/path/to/model python providers/factory.py \
  --request examples/provider_request.json \
  --instances configs/model_instance_registry.json \
  --model-id local.qwen2_5_1_5b_instruct
```

## Current limitations

- Local provider is text-only.
- Local provider loads model weights in-process.
- No streaming yet.
- No model-level concurrency guard yet.
- Image/video/audio generation adapters are not implemented yet.
- Provider-specific tokenizer reconciliation is not implemented yet.
- Provider health probing is basic.

## Next steps

- Add model-decided Agent tool loop.
- Add streaming support.
- Add image/video/audio provider adapter interfaces.
- Add provider usage reconciliation after provider calls.
- Add local model concurrency and cache controls.
