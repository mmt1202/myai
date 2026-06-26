from __future__ import annotations

import argparse
import importlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from providers.base import BaseProvider, ProviderError, chunk_text, output_text_block, provider_stream_event, response_envelope, text_from_content_blocks
from services.token_counter import estimate_request_usage, estimate_text_tokens

CacheKey = tuple[str, str | None]

_MODEL_CACHE: dict[CacheKey, dict[str, Any]] = {}
_CACHE_LOCK = threading.RLock()
_LOAD_LOCK = threading.RLock()
_GENERATION_LOCKS: dict[CacheKey, threading.RLock] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_adapter_path(adapter_path: str | None) -> str | None:
    return str(adapter_path) if adapter_path else None


def local_cache_key(model_path: str, adapter_path: str | None = None) -> CacheKey:
    return (str(model_path), normalize_adapter_path(adapter_path))


def get_generation_lock(cache_key: CacheKey) -> threading.RLock:
    with _CACHE_LOCK:
        lock = _GENERATION_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.RLock()
            _GENERATION_LOCKS[cache_key] = lock
        return lock


def clear_model_cache() -> None:
    with _CACHE_LOCK:
        _MODEL_CACHE.clear()
        _GENERATION_LOCKS.clear()


def cache_stats() -> dict[str, Any]:
    with _CACHE_LOCK:
        entries = []
        for (model_path, adapter_path), entry in _MODEL_CACHE.items():
            entries.append(
                {
                    "model_path": model_path,
                    "adapter_path": adapter_path,
                    "loaded_at": entry.get("loaded_at"),
                    "last_used_at": entry.get("last_used_at"),
                    "load_count": entry.get("load_count", 1),
                    "hit_count": entry.get("hit_count", 0),
                    "generation_count": entry.get("generation_count", 0),
                    "stream_generation_count": entry.get("stream_generation_count", 0),
                    "in_use": entry.get("in_use", 0),
                }
            )
        return {"entry_count": len(entries), "entries": entries}


def cache_entry(cache_key: CacheKey) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        return _MODEL_CACHE.get(cache_key)


def cache_enabled_from_request(default: bool, request: dict[str, Any]) -> bool:
    if "use_cache" in request:
        return bool(request.get("use_cache"))
    if "disable_cache" in request:
        return not bool(request.get("disable_cache"))
    return default


def serialize_generation_from_request(default: bool, request: dict[str, Any]) -> bool:
    if "serialize_generation" in request:
        return bool(request.get("serialize_generation"))
    return default


def stream_supported_from_module(module: Any) -> bool:
    return callable(getattr(module, "generate_text_stream", None))


class LocalTextProvider(BaseProvider):
    provider_name = "local"

    def __init__(
        self,
        model_instance: dict[str, Any] | None = None,
        *,
        model_path: str | None = None,
        adapter_path: str | None = None,
        system_prompt_file: str | None = None,
        use_cache: bool = True,
        serialize_generation: bool = True,
    ) -> None:
        super().__init__(model_instance=model_instance)
        runtime_config = (model_instance or {}).get("runtime_config") or {}
        self.model_path = model_path or os.environ.get("FOUNDATION_LOCAL_MODEL_PATH") or runtime_config.get("model_path")
        self.adapter_path = adapter_path or os.environ.get("FOUNDATION_LOCAL_ADAPTER_PATH") or runtime_config.get("adapter_path")
        self.system_prompt_file = system_prompt_file or os.environ.get("FOUNDATION_LOCAL_SYSTEM_PROMPT") or runtime_config.get("system_prompt_file")
        self.use_cache = use_cache
        self.serialize_generation = serialize_generation

    def provider_model(self) -> str:
        return str(self.model_instance.get("model_name") or self.model_path or self.model_id())

    def health(self) -> dict[str, Any]:
        return {
            **super().health(),
            "model_path_configured": bool(self.model_path),
            "adapter_path_configured": bool(self.adapter_path),
            "use_cache": self.use_cache,
            "serialize_generation": self.serialize_generation,
            "streaming": True,
            "cache": cache_stats(),
        }

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

    def load_runtime(self, model_path: str, adapter_path: str | None, *, use_cache: bool | None = None) -> tuple[Any, Any, Any]:
        should_cache = self.use_cache if use_cache is None else use_cache
        key = local_cache_key(model_path, adapter_path)
        if should_cache:
            with _CACHE_LOCK:
                entry = _MODEL_CACHE.get(key)
                if entry:
                    entry["last_used_at"] = now_iso()
                    entry["hit_count"] = int(entry.get("hit_count") or 0) + 1
                    return entry["runtime"]
        with _LOAD_LOCK:
            if should_cache:
                with _CACHE_LOCK:
                    entry = _MODEL_CACHE.get(key)
                    if entry:
                        entry["last_used_at"] = now_iso()
                        entry["hit_count"] = int(entry.get("hit_count") or 0) + 1
                        return entry["runtime"]
            module = importlib.import_module("inference.model_utils")
            runtime = module.load_model(model_path, adapter_path)
            if should_cache:
                with _CACHE_LOCK:
                    existing = _MODEL_CACHE.get(key)
                    previous_load_count = int((existing or {}).get("load_count") or 0)
                    _MODEL_CACHE[key] = {
                        "runtime": runtime,
                        "loaded_at": now_iso(),
                        "last_used_at": now_iso(),
                        "load_count": previous_load_count + 1,
                        "hit_count": 0,
                        "generation_count": 0,
                        "stream_generation_count": 0,
                        "in_use": 0,
                    }
            return runtime

    def mark_generation_start(self, cache_key: CacheKey) -> None:
        with _CACHE_LOCK:
            entry = _MODEL_CACHE.get(cache_key)
            if entry:
                entry["in_use"] = int(entry.get("in_use") or 0) + 1
                entry["last_used_at"] = now_iso()

    def mark_generation_end(self, cache_key: CacheKey, *, streamed: bool = False) -> None:
        with _CACHE_LOCK:
            entry = _MODEL_CACHE.get(cache_key)
            if entry:
                entry["in_use"] = max(0, int(entry.get("in_use") or 0) - 1)
                counter = "stream_generation_count" if streamed else "generation_count"
                entry[counter] = int(entry.get(counter) or 0) + 1
                entry["last_used_at"] = now_iso()

    def generation_context(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = self.build_prompt(request)
        model_path, adapter_path, system_prompt_file = self.resolved_paths(request)
        return {
            "prompt": prompt,
            "model_path": model_path,
            "adapter_path": adapter_path,
            "system_prompt_file": system_prompt_file,
            "max_new_tokens": int(request.get("max_new_tokens") or request.get("max_output_tokens") or 512),
            "temperature": float(request.get("temperature", 0.2)),
            "should_cache": cache_enabled_from_request(self.use_cache, request),
            "should_serialize": serialize_generation_from_request(self.serialize_generation, request),
        }

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        context = self.generation_context(request)
        prompt = context["prompt"]
        model_path = context["model_path"]
        adapter_path = context["adapter_path"]
        system_prompt_file = context["system_prompt_file"]
        max_new_tokens = context["max_new_tokens"]
        temperature = context["temperature"]
        should_cache = context["should_cache"]
        should_serialize = context["should_serialize"]
        if request.get("dry_run") or request.get("dry_run_provider"):
            usage = estimate_request_usage(request, expected_output_tokens=max_new_tokens)
            cache_key = local_cache_key(str(model_path), str(adapter_path) if adapter_path else None) if model_path else None
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
                    "use_cache": should_cache,
                    "serialize_generation": should_serialize,
                    "stream": bool(request.get("stream")),
                    "cache_hit": bool(cache_key and cache_entry(cache_key)),
                    "cache": cache_stats(),
                },
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model=self.provider_model_info(),
                usage=usage,
                warnings=["dry_run_no_local_model_load"],
            )
        if not model_path:
            raise ProviderError("model_not_found", "local provider requires model_path or FOUNDATION_LOCAL_MODEL_PATH")
        module = importlib.import_module("inference.model_utils")
        key = local_cache_key(str(model_path), str(adapter_path) if adapter_path else None)
        tokenizer, model, _ = self.load_runtime(str(model_path), str(adapter_path) if adapter_path else None, use_cache=should_cache)
        system_prompt = request.get("system") or module.load_system_prompt(str(system_prompt_file) if system_prompt_file else None)
        lock = get_generation_lock(key) if should_serialize else None
        if lock:
            with lock:
                self.mark_generation_start(key)
                try:
                    text = module.generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt)
                finally:
                    self.mark_generation_end(key)
        else:
            self.mark_generation_start(key)
            try:
                text = module.generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt)
            finally:
                self.mark_generation_end(key)
        usage = estimate_request_usage(request, expected_output_tokens=estimate_text_tokens(text))
        return response_envelope(
            status="ok",
            output={"content": [output_text_block(text)], "cache": cache_stats()},
            request_id_value=request.get("request_id"),
            trace_id=request.get("trace_id"),
            model=self.provider_model_info(),
            usage=usage,
        )

    def stream_generate(self, request: dict[str, Any]) -> Iterator[dict[str, Any]]:
        context = self.generation_context(request)
        request_id_value = request.get("request_id")
        trace_id = request.get("trace_id")
        model_info = self.provider_model_info()
        yield provider_stream_event(
            "provider_stream_started",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            metadata={"provider": self.provider_name, "streaming_mode": "local_text"},
        )
        if request.get("dry_run") or request.get("dry_run_provider"):
            prompt = context["prompt"]
            chunk_chars = int(request.get("stream_chunk_chars") or 128)
            for index, delta in enumerate(chunk_text(prompt or "dry_run", chunk_chars=chunk_chars)):
                yield provider_stream_event("provider_stream_delta", request_id_value=request_id_value, trace_id=trace_id, model=model_info, delta=delta, index=index, metadata={"dry_run": True})
            usage = estimate_request_usage(request, expected_output_tokens=context["max_new_tokens"])
            yield provider_stream_event(
                "provider_stream_completed",
                request_id_value=request_id_value,
                trace_id=trace_id,
                model=model_info,
                usage=usage,
                output={"dry_run": True, "cache": cache_stats()},
                done=True,
                metadata={"dry_run": True},
            )
            return
        model_path = context["model_path"]
        adapter_path = context["adapter_path"]
        system_prompt_file = context["system_prompt_file"]
        if not model_path:
            raise ProviderError("model_not_found", "local provider requires model_path or FOUNDATION_LOCAL_MODEL_PATH")
        module = importlib.import_module("inference.model_utils")
        key = local_cache_key(str(model_path), str(adapter_path) if adapter_path else None)
        tokenizer, model, _ = self.load_runtime(str(model_path), str(adapter_path) if adapter_path else None, use_cache=context["should_cache"])
        system_prompt = request.get("system") or module.load_system_prompt(str(system_prompt_file) if system_prompt_file else None)
        lock = get_generation_lock(key) if context["should_serialize"] else None
        collected: list[str] = []

        def emit_stream() -> Iterator[dict[str, Any]]:
            if stream_supported_from_module(module) and not request.get("force_chunked_stream"):
                for index, delta in enumerate(module.generate_text_stream(tokenizer, model, context["prompt"], context["max_new_tokens"], context["temperature"], system_prompt)):
                    collected.append(str(delta))
                    yield provider_stream_event("provider_stream_delta", request_id_value=request_id_value, trace_id=trace_id, model=model_info, delta=str(delta), index=index)
            else:
                text = module.generate_text(tokenizer, model, context["prompt"], context["max_new_tokens"], context["temperature"], system_prompt)
                for index, delta in enumerate(chunk_text(text, chunk_chars=int(request.get("stream_chunk_chars") or 128))):
                    collected.append(delta)
                    yield provider_stream_event("provider_stream_delta", request_id_value=request_id_value, trace_id=trace_id, model=model_info, delta=delta, index=index, metadata={"fallback_chunked_stream": True})

        if lock:
            with lock:
                self.mark_generation_start(key)
                try:
                    yield from emit_stream()
                finally:
                    self.mark_generation_end(key, streamed=True)
        else:
            self.mark_generation_start(key)
            try:
                yield from emit_stream()
            finally:
                self.mark_generation_end(key, streamed=True)
        text = "".join(collected)
        usage = estimate_request_usage(request, expected_output_tokens=estimate_text_tokens(text))
        yield provider_stream_event(
            "provider_stream_completed",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            output={"content": [output_text_block(text)], "cache": cache_stats()},
            usage=usage,
            done=True,
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
    parser.add_argument("--no-serialize-generation", action="store_true")
    parser.add_argument("--cache-stats", action="store_true")
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.clear_cache:
        clear_model_cache()
    if args.cache_stats:
        print(json.dumps(cache_stats(), ensure_ascii=False, indent=2))
        return 0
    request = load_json(Path(args.request))
    if args.stream:
        request["stream"] = True
    instance = load_json(Path(args.model_instance)) if args.model_instance else {}
    provider = LocalTextProvider(
        instance,
        model_path=args.model_path,
        adapter_path=args.adapter_path,
        system_prompt_file=args.system_prompt_file,
        use_cache=not args.no_cache,
        serialize_generation=not args.no_serialize_generation,
    )
    try:
        result: Any = list(provider.stream_generate(request)) if args.stream else provider.generate(request)
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
