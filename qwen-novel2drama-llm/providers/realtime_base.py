from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Iterator

from providers.base import ProviderError, provider_stream_event

PROVIDER_NATIVE_TEST_PROTOCOLS = {"provider_native_test", "openai_realtime_test", "openai_responses_test"}
PROVIDER_NATIVE_PROTOCOLS = PROVIDER_NATIVE_TEST_PROTOCOLS | {"openai_realtime", "openai_responses"}


def tool_call_id(tool_call: dict[str, Any], tool_result: dict[str, Any] | None = None) -> str:
    result = tool_result or {}
    return str(tool_call.get("call_id") or tool_call.get("id") or tool_call.get("tool_call_id") or result.get("call_id") or result.get("tool_call_id") or "unknown_tool_call")


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
    def __init__(self, *, protocol: str) -> None:
        self.protocol = protocol

    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        raise NotImplementedError


class TestDoubleContinuationAdapter(ProviderNativeContinuationAdapter):
    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        result_text = tool_result_text(tool_result)
        text = f"tool_result_received:{tool_call_id(tool_call, tool_result)}:{result_text}"
        yield continuation_started_event(request, model, tool_call, tool_result, protocol=self.protocol, stream_context=stream_context)
        yield continuation_delta_event(request, model, text, index=0, protocol=self.protocol, tool_call=tool_call, tool_result=tool_result)
        yield continuation_completed_event(request, model, tool_call, tool_result, protocol=self.protocol, text=text)


class OpenAIResponsesContinuationAdapter(ProviderNativeContinuationAdapter):
    def base_url(self, request: dict[str, Any]) -> str:
        return str(request.get("responses_base_url") or request.get("base_url") or os.environ.get("MODEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")

    def api_key_env(self, request: dict[str, Any]) -> str:
        return str(request.get("api_key_env") or "MODEL_API_KEY")

    def request_headers(self, request: dict[str, Any]) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self.api_key_env(request))
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def response_input(self, request: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None) -> list[dict[str, Any]]:
        base_items = list((stream_context or {}).get("responses_output") or (stream_context or {}).get("response_output") or request.get("input") or [])
        base_items.append({"type": "function_call_output", "call_id": tool_call_id(tool_call, tool_result), "output": tool_result_text(tool_result)})
        return base_items

    def build_payload(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": request.get("model") or model.get("provider_model") or model.get("model_id"), "input": self.response_input(request, tool_call, tool_result, stream_context)}
        if request.get("instructions") or request.get("system"):
            payload["instructions"] = request.get("instructions") or request.get("system")
        if request.get("tools"):
            payload["tools"] = request["tools"]
        if request.get("temperature") is not None:
            payload["temperature"] = request["temperature"]
        if request.get("max_output_tokens") is not None:
            payload["max_output_tokens"] = int(request["max_output_tokens"])
        return payload

    def extract_text(self, data: dict[str, Any]) -> str:
        if data.get("output_text") is not None:
            return str(data.get("output_text") or "")
        parts: list[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("text") is not None:
                    parts.append(str(content.get("text") or ""))
        return "".join(parts)

    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        payload = self.build_payload(request, model, tool_call, tool_result, stream_context)
        yield continuation_started_event(request, model, tool_call, tool_result, protocol=self.protocol, stream_context=stream_context)
        if request.get("dry_run") or request.get("dry_run_provider"):
            text = json.dumps({"dry_run": True, "provider_payload": payload, "url": f"{self.base_url(request)}/responses"}, ensure_ascii=False, sort_keys=True)
            yield continuation_delta_event(request, model, text, index=0, protocol=self.protocol, tool_call=tool_call, tool_result=tool_result)
            yield continuation_completed_event(request, model, tool_call, tool_result, protocol=self.protocol, text=text)
            return
        http_request = urllib.request.Request(f"{self.base_url(request)}/responses", data=json.dumps(payload).encode("utf-8"), headers=self.request_headers(request), method="POST")
        try:
            with urllib.request.urlopen(http_request, timeout=int(request.get("timeout") or 120)) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        text = self.extract_text(data)
        if text:
            yield continuation_delta_event(request, model, text, index=0, protocol=self.protocol, tool_call=tool_call, tool_result=tool_result)
        yield continuation_completed_event(request, model, tool_call, tool_result, protocol=self.protocol, text=text)


class OpenAIRealtimeSessionContinuationAdapter(ProviderNativeContinuationAdapter):
    def continue_with_tool_result(self, request: dict[str, Any], model: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        session = (stream_context or {}).get("realtime_session")
        if session is None:
            raise ProviderError("realtime_session_missing", "openai_realtime continuation requires stream_context.realtime_session", retryable=False, details={"protocol": self.protocol})
        call_id = tool_call_id(tool_call, tool_result)
        output = tool_result_text(tool_result)
        yield continuation_started_event(request, model, tool_call, tool_result, protocol=self.protocol, stream_context={"has_realtime_session": True})
        session.send_json({"type": "conversation.item.create", "item": {"type": "function_call_output", "call_id": call_id, "output": output}})
        session.send_json({"type": "response.create"})
        collected: list[str] = []
        for index, event in enumerate(session.iter_events()):
            event_type = str(event.get("type") or "")
            delta = event.get("delta") or event.get("text") or event.get("transcript") or ""
            if delta and ("delta" in event_type or event_type.endswith("text")):
                collected.append(str(delta))
                yield continuation_delta_event(request, model, str(delta), index=index, protocol=self.protocol, tool_call=tool_call, tool_result=tool_result)
            if event_type in {"response.done", "response.completed"}:
                break
        yield continuation_completed_event(request, model, tool_call, tool_result, protocol=self.protocol, text="".join(collected))


def adapter_for_protocol(protocol: str) -> ProviderNativeContinuationAdapter | None:
    if protocol in PROVIDER_NATIVE_TEST_PROTOCOLS:
        return TestDoubleContinuationAdapter(protocol=protocol)
    if protocol == "openai_responses":
        return OpenAIResponsesContinuationAdapter(protocol=protocol)
    if protocol == "openai_realtime":
        return OpenAIRealtimeSessionContinuationAdapter(protocol=protocol)
    return None
