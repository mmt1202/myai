from __future__ import annotations

import json
from typing import Any, Iterator

from providers.base import provider_stream_event

PROVIDER_NATIVE_TEST_PROTOCOLS = {"provider_native_test", "openai_realtime_test", "openai_responses_test"}
PROVIDER_NATIVE_PROTOCOLS = PROVIDER_NATIVE_TEST_PROTOCOLS | {"openai_realtime", "openai_responses"}


def tool_call_id(tool_call: dict[str, Any], tool_result: dict[str, Any] | None = None) -> str:
    result = tool_result or {}
    return str(tool_call.get("id") or tool_call.get("tool_call_id") or result.get("tool_call_id") or "unknown_tool_call")


def tool_name(tool_call: dict[str, Any], tool_result: dict[str, Any] | None = None) -> str:
    result = tool_result or {}
    function = tool_call.get("function") or {}
    return str(tool_call.get("name") or function.get("name") or result.get("name") or "unknown_tool")


def tool_result_text(tool_result: dict[str, Any]) -> str:
    return json.dumps(tool_result, ensure_ascii=False, sort_keys=True)


def continuation_started_event(request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], *, protocol: str, stream_context: dict[str, Any] | None = None) -> dict[str, Any]:
    return provider_stream_event(
        "provider_stream_continuation_started",
        request_id_value=request.get("request_id"),
        trace_id=request.get("trace_id"),
        model=model,
        output={"tool_call_id": tool_call_id(tool_call, tool_result), "tool_name": tool_name(tool_call, tool_result)},
        metadata={"protocol": protocol, "provider_native": True, "stream_context": stream_context or {}},
    )


def continuation_delta_event(request: dict[str, Any], model: dict[str, Any], delta: str, *, index: int, protocol: str, tool_call: dict[str, Any], tool_result: dict[str, Any]) -> dict[str, Any]:
    return provider_stream_event(
        "provider_stream_continuation_delta",
        request_id_value=request.get("request_id"),
        trace_id=request.get("trace_id"),
        model=model,
        delta=delta,
        index=index,
        metadata={"protocol": protocol, "provider_native": True, "tool_call_id": tool_call_id(tool_call, tool_result)},
    )


def continuation_completed_event(request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], *, protocol: str, text: str) -> dict[str, Any]:
    return provider_stream_event(
        "provider_stream_continuation_completed",
        request_id_value=request.get("request_id"),
        trace_id=request.get("trace_id"),
        model=model,
        output={"content": [{"type": "text", "text": text}], "tool_call_id": tool_call_id(tool_call, tool_result), "tool_name": tool_name(tool_call, tool_result)},
        done=True,
        metadata={"protocol": protocol, "provider_native": True, "tool_call_id": tool_call_id(tool_call, tool_result)},
    )


class ProviderNativeContinuationAdapter:
    """Base adapter for provider-native same-stream tool result continuation.

    A concrete provider should override `continue_with_tool_result` when it can keep
    the provider session/stream open and inject a tool result without starting a new
    provider request. The default test adapter is intentionally deterministic and is
    used only for contract tests.
    """

    def __init__(self, *, protocol: str) -> None:
        self.protocol = protocol

    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        raise NotImplementedError


class TestDoubleContinuationAdapter(ProviderNativeContinuationAdapter):
    """Deterministic provider-native continuation test double.

    This adapter does not call any external provider. It proves that provider-native
    continuation events can pass through the provider factory and Agent stream bridge
    without falling back to a next provider request.
    """

    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        result_text = tool_result_text(tool_result)
        text = f"tool_result_received:{tool_call_id(tool_call, tool_result)}:{result_text}"
        yield continuation_started_event(request, model, tool_call, tool_result, protocol=self.protocol, stream_context=stream_context)
        yield continuation_delta_event(request, model, text, index=0, protocol=self.protocol, tool_call=tool_call, tool_result=tool_result)
        yield continuation_completed_event(request, model, tool_call, tool_result, protocol=self.protocol, text=text)


def adapter_for_protocol(protocol: str) -> ProviderNativeContinuationAdapter | None:
    if protocol in PROVIDER_NATIVE_TEST_PROTOCOLS:
        return TestDoubleContinuationAdapter(protocol=protocol)
    return None
