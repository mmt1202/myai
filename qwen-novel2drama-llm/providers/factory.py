from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

from providers.base import BaseProvider, ProviderError, response_envelope
from providers.local_text import LocalTextProvider
from providers.openai_compatible import OpenAICompatibleProvider


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_model_instance(registry: dict[str, Any], model_id: str) -> dict[str, Any]:
    for item in registry.get("instances", []):
        if item.get("id") == model_id or model_id in item.get("aliases", []):
            return item
    raise KeyError(f"model instance not found: {model_id}")


def build_provider(
    model_instance: dict[str, Any],
    *,
    base_url: str | None = None,
    api_key_env: str = "MODEL_API_KEY",
    timeout: int = 120,
    model_path: str | None = None,
    adapter_path: str | None = None,
    system_prompt_file: str | None = None,
) -> BaseProvider:
    provider = model_instance.get("provider")
    runtime = model_instance.get("runtime")
    if provider == "openai_compatible" or runtime == "http_chat_completions":
        return OpenAICompatibleProvider(model_instance, base_url=base_url, api_key_env=api_key_env, timeout=timeout)
    if provider == "local" or runtime == "transformers":
        return LocalTextProvider(model_instance, model_path=model_path, adapter_path=adapter_path, system_prompt_file=system_prompt_file)
    raise ProviderError("provider_not_supported", f"unsupported provider/runtime: {provider}/{runtime}")


def provider_for_request(
    request: dict[str, Any],
    registry: dict[str, Any],
    *,
    model_id: str | None = None,
    base_url: str | None = None,
    api_key_env: str = "MODEL_API_KEY",
    timeout: int = 120,
) -> BaseProvider:
    selected_model = model_id or request.get("model_id") or request.get("model")
    if not selected_model:
        raise ProviderError("model_not_found", "model_id is required for provider factory")
    instance = find_model_instance(registry, str(selected_model))
    return build_provider(
        instance,
        base_url=base_url,
        api_key_env=api_key_env,
        timeout=timeout,
        model_path=request.get("model_path"),
        adapter_path=request.get("adapter_path"),
        system_prompt_file=request.get("system_prompt_file"),
    )


def generate_with_registry(
    request: dict[str, Any],
    registry: dict[str, Any],
    *,
    model_id: str | None = None,
    base_url: str | None = None,
    api_key_env: str = "MODEL_API_KEY",
    timeout: int = 120,
) -> dict[str, Any]:
    provider = provider_for_request(request, registry, model_id=model_id, base_url=base_url, api_key_env=api_key_env, timeout=timeout)
    return provider.generate(request)


def stream_generate_with_registry(
    request: dict[str, Any],
    registry: dict[str, Any],
    *,
    model_id: str | None = None,
    base_url: str | None = None,
    api_key_env: str = "MODEL_API_KEY",
    timeout: int = 120,
) -> Iterator[dict[str, Any]]:
    provider = provider_for_request(request, registry, model_id=model_id, base_url=base_url, api_key_env=api_key_env, timeout=timeout)
    yield from provider.stream_generate(request)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--instances", default="configs/model_instance_registry.json")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    registry = load_json(Path(args.instances))
    try:
        result: Any = (
            list(stream_generate_with_registry(request, registry, model_id=args.model_id, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout))
            if args.stream
            else generate_with_registry(request, registry, model_id=args.model_id, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout)
        )
    except ProviderError as exc:
        result = response_envelope(status="failed", request_id_value=request.get("request_id"), trace_id=request.get("trace_id"), error=exc.to_error(request.get("trace_id"), request.get("request_id")))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    status = result[-1].get("event_type") if isinstance(result, list) and result else result.get("status")
    return 0 if status in {"ok", "provider_stream_completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
