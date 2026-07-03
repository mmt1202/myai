from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def stream_chunk_id() -> str:
    return f"chunk_{uuid.uuid4().hex}"


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def to_error(self, trace_id: str | None = None, request_id_value: str | None = None) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
            "trace_id": trace_id,
            "request_id": request_id_value,
        }


def text_from_content_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "subtitle", "reasoning_hint", "tool_result"}:
            parts.append(str(block.get("text") or ""))
        elif block_type == "metadata":
            parts.append(json.dumps(block.get("metadata") or {}, ensure_ascii=False))
        elif block_type in {"image", "video", "audio", "file", "url"}:
            parts.append(f"[{block_type}: {block.get('uri') or block.get('file_id') or block.get('filename') or 'inline'}]")
    return "\n".join(part for part in parts if part)


def output_text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def response_envelope(
    *,
    status: str,
    output: Any = None,
    request_id_value: str | None = None,
    trace_id: str | None = None,
    model: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    route: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id_value or request_id(),
        "trace_id": trace_id,
        "status": status,
        "model": model or {},
        "usage": usage or {},
        "cost": cost or {},
        "output": output,
        "warnings": warnings or [],
        "error": error,
        "route": route or {},
        "created_at": now_iso(),
    }


def nested_int(raw: dict[str, Any], *paths: tuple[str, ...]) -> int:
    for path in paths:
        value: Any = raw
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value is not None:
            return int(value or 0)
    return 0


def normalize_usage(raw_usage: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw_usage or {}
    input_tokens = int(raw.get("prompt_tokens") or raw.get("input_tokens") or 0)
    output_tokens = int(raw.get("completion_tokens") or raw.get("output_tokens") or 0)
    reasoning_tokens = int(raw.get("reasoning_tokens") or 0) or nested_int(raw, ("output_tokens_details", "reasoning_tokens"), ("completion_tokens_details", "reasoning_tokens"))
    cached_input_tokens = int(raw.get("cached_input_tokens") or 0) or nested_int(raw, ("input_tokens_details", "cached_tokens"), ("prompt_tokens_details", "cached_tokens"))
    total_tokens = int(raw.get("total_tokens") or input_tokens + output_tokens + reasoning_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_input_tokens": cached_input_tokens,
        "total_tokens": total_tokens,
    }


def provider_stream_event(
    event_type: str,
    *,
    request_id_value: str | None = None,
    trace_id: str | None = None,
    model: dict[str, Any] | None = None,
    delta: str | None = None,
    output: Any = None,
    usage: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    index: int | None = None,
    done: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": stream_chunk_id(),
        "created_at": now_iso(),
        "request_id": request_id_value,
        "trace_id": trace_id,
        "event_type": event_type,
        "index": index,
        "model": model or {},
        "delta": delta,
        "output": output,
        "usage": usage or {},
        "error": error,
        "done": done,
        "metadata": metadata or {},
    }


def continuation_capability(model_instance: dict[str, Any] | None) -> dict[str, Any]:
    instance = model_instance or {}
    runtime_config = instance.get("runtime_config") or {}
    continuation = runtime_config.get("bidirectional_tool_continuation") or runtime_config.get("same_stream_tool_result_injection") or {}
    if isinstance(continuation, bool):
        continuation = {"supported": continuation}
    if not isinstance(continuation, dict):
        continuation = {}
    supported = bool(continuation.get("supported"))
    protocol = continuation.get("protocol") or "unsupported"
    return {
        "supported": supported,
        "protocol": protocol if supported else "unsupported",
        "mode": continuation.get("mode") or ("provider_native" if supported else "fallback_next_provider_request"),
        "notes": continuation.get("notes") or "Provider adapter does not support same-stream tool-result injection.",
    }


def text_from_provider_response(response: dict[str, Any]) -> str:
    output = response.get("output") or {}
    content = output.get("content") or [] if isinstance(output, dict) else []
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    if parts:
        return "".join(parts)
    if isinstance(output, dict) and output.get("text"):
        return str(output.get("text"))
    return ""


def chunk_text(text: str, *, chunk_chars: int = 128) -> list[str]:
    size = max(1, int(chunk_chars or 128))
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


class BaseProvider(ABC):
    provider_name = "base"

    def __init__(self, model_instance: dict[str, Any] | None = None) -> None:
        self.model_instance = model_instance or {}

    def model_id(self) -> str:
        return str(self.model_instance.get("id") or self.model_instance.get("model_name") or "unknown")

    def provider_model(self) -> str:
        return str(self.model_instance.get("model_name") or self.model_id())

    def provider_model_info(self) -> dict[str, Any]:
        return {"model_id": self.model_id(), "provider": self.provider_name, "provider_model": self.provider_model()}

    def health(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "model_id": self.model_id(), "status": "configured" if self.model_instance else "unconfigured"}

    def supports_capability(self, capability: str) -> bool:
        return capability in set(self.model_instance.get("capabilities") or [])

    def supports_modalities(self, input_modalities: set[str], output_modality: str | None = None) -> bool:
        inputs = set(self.model_instance.get("input_modalities") or [])
        outputs = set(self.model_instance.get("output_modalities") or [])
        if not input_modalities.issubset(inputs):
            return False
        if output_modality and output_modality not in outputs:
            return False
        return True

    def continuation_capability(self) -> dict[str, Any]:
        return continuation_capability(self.model_instance)

    def supports_bidirectional_tool_continuation(self) -> bool:
        return bool(self.continuation_capability().get("supported"))

    @abstractmethod
    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def stream_generate(self, request: dict[str, Any]) -> Iterator[dict[str, Any]]:
        request_id_value = request.get("request_id")
        trace_id = request.get("trace_id")
        model = self.provider_model_info()
        yield provider_stream_event("provider_stream_started", request_id_value=request_id_value, trace_id=trace_id, model=model)
        response = self.generate(request)
        text = text_from_provider_response(response)
        chunk_chars = int(request.get("stream_chunk_chars") or 128)
        for index, delta in enumerate(chunk_text(text, chunk_chars=chunk_chars)):
            yield provider_stream_event("provider_stream_delta", request_id_value=request_id_value, trace_id=trace_id, model=model, delta=delta, index=index)
        yield provider_stream_event(
            "provider_stream_completed",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model,
            output=response.get("output"),
            usage=response.get("usage") or {},
            done=True,
            metadata={"fallback_full_response": True},
        )

    def continue_stream_with_tool_result(self, request: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        capability = self.continuation_capability()
        raise ProviderError(
            "bidirectional_tool_continuation_unsupported",
            "provider does not support same-stream tool-result injection",
            retryable=False,
            details={"capability": capability, "tool_call_id": tool_call.get("id") or tool_result.get("tool_call_id")},
        )
