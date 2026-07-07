# Provider Candidate Adapters

MyAI Foundation treats OpenAI, DeepSeek, Qwen/DashScope, Claude, Gemini and local models as configurable provider candidates. No provider is hard-coded as the only primary model.

## Adapter classes

```text
providers/openai_responses.py       -> OpenAI Responses API runtime
providers/openai_compatible.py      -> OpenAI-compatible chat-completions runtime
providers/local_text.py             -> local transformers runtime
providers/factory.py                -> registry-driven provider builder
scripts/provider_candidate_smoke.py -> generic dry-run/live smoke
```

## Registry-driven env config

Each external provider candidate should declare runtime config in `configs/model_instance_registry.json`:

```json
{
  "id": "external.deepseek.chat",
  "provider": "deepseek",
  "runtime": "http_chat_completions",
  "runtime_config": {
    "base_url_env": "DEEPSEEK_BASE_URL",
    "api_key_env": "DEEPSEEK_API_KEY",
    "model_name_env": "DEEPSEEK_MODEL"
  }
}
```

The OpenAI-compatible adapter now reads these provider-specific env names. The factory no longer replaces them with the generic `MODEL_API_KEY` unless explicitly requested by the caller.

## Supported provider candidates

Current registry candidates include:

```text
external.openai.primary       -> runtime=openai_responses
external.deepseek.chat        -> runtime=http_chat_completions
external.qwen_dashscope.omni  -> runtime=http_chat_completions
external.anthropic.claude     -> runtime=http_chat_completions via gateway-compatible endpoint
external.gemini.multimodal    -> runtime=http_chat_completions via gateway-compatible endpoint
local.qwen2_5_1_5b_instruct  -> runtime=transformers
```

Claude and Gemini can be routed through gateway-compatible endpoints when their direct native SDK adapters are not configured. Native SDK adapters can be added later without changing the model routing policy shape.

## Dry run

Dry run never calls the network:

```bash
python scripts/provider_candidate_smoke.py --model-id external.deepseek.chat
python scripts/provider_candidate_smoke.py --model-id external.qwen_dashscope.omni --stream
```

The dry-run result includes provider payload, target URL and env metadata.

## Live smoke

Live smoke is environment gated:

```bash
set DEEPSEEK_BASE_URL=https://api.deepseek.example/v1
set DEEPSEEK_API_KEY=...
set DEEPSEEK_MODEL=...
python scripts/provider_candidate_smoke.py --model-id external.deepseek.chat --live
python scripts/provider_candidate_smoke.py --model-id external.deepseek.chat --live --stream
```

If the required API key is missing, live smoke returns `skipped`, not failed. If a key is configured and the provider call fails, it returns `failed`.

## OpenAI-compatible payload support

The OpenAI-compatible adapter supports:

```text
model
messages
max_tokens from max_output_tokens
temperature
top_p
frequency_penalty
presence_penalty
stop
response_format
seed
metadata
tools
tool_choice
stream
stream_options
```

## Stream support

The adapter supports SSE-style chat completion streaming:

```text
data: {"choices":[{"delta":{"content":"..."}}]}
data: {"choices":[{"delta":{"tool_calls":[...]}}]}
data: [DONE]
```

It emits Foundation stream events:

```text
provider_stream_started
provider_stream_delta
provider_stream_tool_call_delta
provider_stream_completed
```

## Boundaries

- Repository adapter support does not mean real provider accounts, base URLs, model names, API keys or billing are configured.
- Claude/Gemini native SDK semantics are not implemented here; current support assumes gateway-compatible chat-completions endpoints.
- Provider-specific advanced features should be added behind provider-specific runtime adapters, not by hard-coding one provider as global primary.
