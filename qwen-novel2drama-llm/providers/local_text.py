from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Any

from providers.base import BaseProvider, ProviderError, output_text_block, response_envelope, text_from_content_blocks
from services.token_counter import estimate_request_usage, estimate_text_tokens

_MODEL_CACHE: dict[tuple[str, str | None], tuple[Any, Any, Any]] = {}


class LocalTextProvider(BaseProvider):
    provider_name = "local"

    def __init__(self, model_instance: dict[str, Any] | None = None, *, model_path: str | None = None, adapter_path: str | None = None, system_prompt_file: str | None = None, use_cache: bool = True) -> None:
        super().__init__(model_instance=model_instance)
        runtime_config = (model_instance or {}).get("runtime_config") or {}
        self.model_path = model_path or os.environ.get("FOUNDATION_LOCAL_MODEL_PATH") or runtime_config.get("model_path")
        self.adapter_path = adapter_path or os.environ.get("FOUNDATION_LOCAL_ADAPTER_PATH") or runtime_config.get("adapter_path")
        self.system_prompt_file = system_prompt_file or os.environ.get("FOUNDATION_LOCAL_SYSTEM_PROMPT") or runtime_config.get("system_prompt_file")
        self.use_cache = use_cache

    def provider_model(self) -> str:
        return str(self.model_instance.get("model_name") or self.model_path or self.model_id())

    def build_prompt(self, request: dict[str, Any]) -> str:
        text = text_from_content_blocks(request.get("input") or [])
        if text:
            return text
        return str(request.get("task") or request.get("prompt") or "")

    def resolved_paths(self, request: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        return (
            request.get("model_path") or self.model_path,
            request.get("adapter_path") or self.adapter_path,
            request.get("system_prompt_file") or self.system_prompt_file,
        )

    def load_runtime(self, model_path: str, adapter_path: str | None) -> tuple[Any, Any, Any]:
        cache_key = (model_path, adapter_path)
        if self.use_cache and cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key]
        module = importlib.import_module("inference.model_utils")
        runtime = module.load_model(model_path, adapter_path)
        if self.use_cache:
            _MODEL_CACHE[cache_key] = runtime
        return runtime

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = self.build_prompt(request)
        model_path, adapter_path, system_prompt_file = self.resolved_paths(request)
        max_new_tokens = int(request.get("max_new_tokens") or request.get("max_output_tokens") or 512)
        temperature = float(request.get("temperature", 0.2))
        if request.get("dry_run") or request.get("dry_run_provider"):
            usage = estimate_request_usage(request, expected_output_tokens=max_new_tokens)
            return response_envelope(
                status="ok",
                output={
                    "dry_run": True,
                    "provider": self.provider_name,
                    "prompt": prompt,
                    "model_path": model_path,
                    "adapter_path": adapter_path,
                    "max_new_tokens": max_new_tokens,
                    "temperature": temperature,
                },
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": self.provider_model()},
                usage=usage,
                warnings=["dry_run_no_local_model_load"],
            )
        if not model_path:
            raise ProviderError("model_not_found", "local provider requires model_path or FOUNDATION_LOCAL_MODEL_PATH")
        module = importlib.import_module("inference.model_utils")
        tokenizer, model, _ = self.load_runtime(str(model_path), str(adapter_path) if adapter_path else None)
        system_prompt = request.get("system") or module.load_system_prompt(str(system_prompt_file) if system_prompt_file else None)
        text = module.generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt)
        usage = estimate_request_usage(request, expected_output_tokens=estimate_text_tokens(text))
        return response_envelope(
            status="ok",
            output={"content": [output_text_block(text)]},
            request_id_value=request.get("request_id"),
            trace_id=request.get("trace_id"),
            model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": self.provider_model()},
            usage=usage,
        )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--model-instance", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--adapter-path", default=None)
    parser.add_argument("--system-prompt-file", default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    instance = load_json(Path(args.model_instance)) if args.model_instance else {}
    provider = LocalTextProvider(instance, model_path=args.model_path, adapter_path=args.adapter_path, system_prompt_file=args.system_prompt_file, use_cache=not args.no_cache)
    try:
        result = provider.generate(request)
    except ProviderError as exc:
        result = response_envelope(status="failed", request_id_value=request.get("request_id"), trace_id=request.get("trace_id"), error=exc.to_error(request.get("trace_id"), request.get("request_id")))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
