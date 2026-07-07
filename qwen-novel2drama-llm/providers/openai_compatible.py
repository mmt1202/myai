from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator

from providers.base import BaseProvider, ProviderError, continuation_capability, normalize_usage, output_text_block, provider_stream_event, response_envelope, text_from_content_blocks
from providers.realtime_base import PROVIDER_NATIVE_PROTOCOLS, adapter_for_protocol

GENERIC_API_KEY_ENV = "MODEL_API_KEY"
GENERIC_BASE_URL_ENV = "MODEL_BASE_URL"
GENERIC_MODEL_ENV = "MODEL_NAME"


class OpenAICompatibleProvider(BaseProvider):
    provider_name = "openai_compatible"

    def __init__(self, model_instance: dict[str, Any] | None = None, *, base_url: str | None = None, api_key_env: str | None = None, timeout: int = 120) -> None:
        super().__init__(model_instance=model_instance)
        runtime_config = self.model_instance.get("runtime_config") or {}
        configured_base_url_env = runtime_config.get("base_url_env") or GENERIC_BASE_URL_ENV
        configured_api_key_env = runtime_config.get("api_key_env") or GENERIC_API_KEY_ENV
        self.model_name_env = runtime_config.get("model_name_env") or GENERIC_MODEL_ENV
        self.base_url_env = configured_base_url_env
        self.api_key_env = configured_api_key_env if api_key_env in {None, GENERIC_API_KEY_ENV} else api_key_env
        self.base_url = (base_url or os.environ.get(self.base_url_env) or os.environ.get(GENERIC_BASE_URL_ENV) or "http://localhost:8000/v1").rstrip("/")
        self.timeout = timeout

    def provider_model(self) -> str:
        configured = os.environ.get(self.model_name_env)
        if configured:
            return configured
        model_name = str(self.model_instance.get("model_name") or "")
        if model_name.startswith("${") and model_name.endswith("}"):
            return self.model_id()
        return model_name or self.model_id()

    def requires_api_key(self) -> bool:
        return self.model_instance.get("provider") != "local" and not self.base_url.startswith("http://localhost") and not self.base_url.startswith("http://127.0.0.1")

    def continuation_capability(self) -> dict[str, Any]:
        capability = continuation_capability(self.model_instance)
        protocol = str(capability.get("protocol") or "unsupported")
        if capability.get("supported") and protocol in PROVIDER_NATIVE_PROTOCOLS:
            return {**capability, "mode": "provider_native", "provider": self.provider_name, "adapter": "openai_compatible_native_continuation"}
        return capability

    def build_messages(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        system_text = request.get("system")
        if system_text:
            messages.append({"role": "system", "content": str(system_text)})
        developer_text = request.get("developer")
        if developer_text:
            messages.append({"role": "system", "content": str(developer_text)})
        content_text = text_from_content_blocks(request.get("input") or [])
        messages.append({"role": "user", "content": content_text or str(request.get("task") or "")})
        return messages

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": request.get("model") or self.provider_model(),
            "messages": self.build_messages(request),
            "temperature": float(request.get("temperature", 0.2)),
        }
        if request.get("max_output_tokens") is not None:
            payload["max_tokens"] = int(request["max_output_tokens"])
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop", "response_format", "seed", "metadata"):
            if request.get(key) is not None:
                payload[key] = request[key]
        if request.get("tools"):
            payload["tools"] = request["tools"]
        if request.get("tool_choice"):
            payload["tool_choice"] = request["tool_choice"]
        if request.get("stream"):
            payload["stream"] = True
            if request.get("stream_options"):
                payload["stream_options"] = request["stream_options"]
            elif request.get("stream_include_usage"):
                payload["stream_options"] = {"include_usage": True}
        return payload

    def request_headers(self) -> dict[str, str]:
        api_key = os.environ.get(self.api_key_env)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_http_request(self, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self.request_headers(),
            method="POST",
        )

    def is_dry_run(self, request: dict[str, Any]) -> bool:
        return bool(request.get("dry_run") or request.get("dry_run_provider"))

    def provider_env(self) -> dict[str, Any]:
        return {
            "base_url_env": self.base_url_env,
            "base_url_configured": bool(os.environ.get(self.base_url_env)),
            "api_key_env": self.api_key_env,
            "api_key_configured": bool(os.environ.get(self.api_key_env)),
            "model_name_env": self.model_name_env,
            "model_name_configured": bool(os.environ.get(self.model_name_env)),
        }

    def parse_chat_response(self, data: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("provider_error", "provider returned no choices", details={"raw": data})
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage = normalize_usage(data.get("usage") or {})
        return response_envelope(
            status="ok",
            output={"content": [output_text_block(text)], "raw_message": message},
            request_id_value=request.get("request_id"),
            trace_id=request.get("trace_id"),
            model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": data.get("model") or self.provider_model()},
            usage=usage,
        )

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = self.build_payload({**request, "stream": False})
        if self.is_dry_run(request):
            return response_envelope(
                status="ok",
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}/chat/completions", "env": self.provider_env()},
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": payload["model"]},
                warnings=["dry_run_no_provider_call"],
            )
        if self.requires_api_key() and not os.environ.get(self.api_key_env):
            raise ProviderError("provider_auth_missing", f"missing API key env: {self.api_key_env}", retryable=False)
        http_request = self.build_http_request(payload)
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        return self.parse_chat_response(data, request)

    def iter_sse_json(self, response: Any) -> Iterator[dict[str, Any]]:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line)
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if not line:
                continue
            if line == "[DONE]":
                return
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProviderError("provider_error", f"invalid provider stream chunk: {line}", details={"line": line}) from exc

    def stream_delta_from_chunk(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content is not None:
            return str(content)
        return ""

    def stream_tool_call_deltas_from_chunk(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        choices = data.get("choices") or []
        if not choices:
            return []
        delta = choices[0].get("delta") or {}
        tool_calls = delta.get("tool_calls") or []
        return [item for item in tool_calls if isinstance(item, dict)]

    def stream_finish_reason(self, data: dict[str, Any]) -> str | None:
        choices = data.get("choices") or []
        if not choices:
            return None
        value = choices[0].get("finish_reason")
        return str(value) if value else None

    def tool_call_index(self, item: dict[str, Any], buffer: dict[int, dict[str, Any]]) -> int:
        value = item.get("index")
        if value is None:
            return len(buffer)
        try:
            return int(value)
        except (TypeError, ValueError):
            return len(buffer)

    def update_tool_call_buffer(self, buffer: dict[int, dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
        index = self.tool_call_index(item, buffer)
        entry = buffer.setdefault(index, {"index": index, "id": None, "type": "function", "function": {"name": "", "arguments": ""}})
        if item.get("id"):
            entry["id"] = str(item["id"])
        if item.get("type"):
            entry["type"] = str(item["type"])
        function_delta = item.get("function") or {}
        if isinstance(function_delta, dict):
            if function_delta.get("name") is not None:
                entry["function"]["name"] = str(entry["function"].get("name") or "") + str(function_delta.get("name") or "")
            if function_delta.get("arguments") is not None:
                entry["function"]["arguments"] = str(entry["function"].get("arguments") or "") + str(function_delta.get("arguments") or "")
        return entry

    def decoded_arguments(self, arguments: str) -> Any:
        if not arguments:
            return None
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return None

    def reconstructed_tool_calls(self, buffer: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        for index in sorted(buffer):
            item = buffer[index]
            function = item.get("function") or {}
            arguments = str(function.get("arguments") or "")
            tool_call = {
                "index": index,
                "id": item.get("id") or f"tool_call_{index}",
                "type": item.get("type") or "function",
                "function": {
                    "name": str(function.get("name") or ""),
                    "arguments": arguments,
                },
            }
            arguments_json = self.decoded_arguments(arguments)
            if arguments_json is not None:
                tool_call["arguments_json"] = arguments_json
            tool_calls.append(tool_call)
        return tool_calls

    def stream_generate(self, request: dict[str, Any]) -> Iterator[dict[str, Any]]:
        stream_request = {**request, "stream": True}
        payload = self.build_payload(stream_request)
        request_id_value = request.get("request_id")
        trace_id = request.get("trace_id")
        model_info = {"model_id": self.model_id(), "provider": self.provider_name, "provider_model": payload["model"]}
        yield provider_stream_event(
            "provider_stream_started",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            metadata={"provider": self.provider_name, "url": f"{self.base_url}/chat/completions", "env": self.provider_env()},
        )
        if self.is_dry_run(request):
            yield provider_stream_event(
                "provider_stream_delta",
                request_id_value=request_id_value,
                trace_id=trace_id,
                model=model_info,
                delta=json.dumps({"dry_run": True, "provider_payload": payload}, ensure_ascii=False),
                index=0,
                metadata={"dry_run": True},
            )
            yield provider_stream_event(
                "provider_stream_completed",
                request_id_value=request_id_value,
                trace_id=trace_id,
                model=model_info,
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}/chat/completions", "env": self.provider_env()},
                done=True,
                metadata={"dry_run": True},
            )
            return
        if self.requires_api_key() and not os.environ.get(self.api_key_env):
            raise ProviderError("provider_auth_missing", f"missing API key env: {self.api_key_env}", retryable=False)
        http_request = self.build_http_request(payload)
        collected: list[str] = []
        tool_call_buffer: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        finish_reason: str | None = None
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                for data in self.iter_sse_json(response):
                    if data.get("usage"):
                        usage = normalize_usage(data.get("usage") or {})
                    reason = self.stream_finish_reason(data)
                    if reason:
                        finish_reason = reason
                    for tool_call_delta in self.stream_tool_call_deltas_from_chunk(data):
                        entry = self.update_tool_call_buffer(tool_call_buffer, tool_call_delta)
                        yield provider_stream_event(
                            "provider_stream_tool_call_delta",
                            request_id_value=request_id_value,
                            trace_id=trace_id,
                            model={**model_info, "provider_model": data.get("model") or model_info["provider_model"]},
                            index=int(entry.get("index") or 0),
                            metadata={
                                "raw_chunk_id": data.get("id"),
                                "finish_reason": reason,
                                "tool_call_delta": tool_call_delta,
                                "tool_call_partial": entry,
                            },
                        )
                    delta = self.stream_delta_from_chunk(data)
                    if not delta:
                        continue
                    collected.append(delta)
                    yield provider_stream_event(
                        "provider_stream_delta",
                        request_id_value=request_id_value,
                        trace_id=trace_id,
                        model={**model_info, "provider_model": data.get("model") or model_info["provider_model"]},
                        delta=delta,
                        index=len(collected) - 1,
                        metadata={"raw_chunk_id": data.get("id"), "finish_reason": reason},
                    )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        text = "".join(collected)
        tool_calls = self.reconstructed_tool_calls(tool_call_buffer)
        output: dict[str, Any] = {"content": [output_text_block(text)], "finish_reason": finish_reason}
        if tool_calls:
            output["tool_calls"] = tool_calls
        yield provider_stream_event(
            "provider_stream_completed",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            output=output,
            usage=usage,
            done=True,
            metadata={"native_stream": True, "tool_call_count": len(tool_calls)},
        )

    def continue_stream_with_tool_result(self, request: dict[str, Any], tool_call: dict[str, Any], tool_result: dict[str, Any], stream_context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        capability = self.continuation_capability()
        protocol = str(capability.get("protocol") or "unsupported")
        adapter = adapter_for_protocol(protocol)
        if not capability.get("supported") or adapter is None:
            raise ProviderError(
                "bidirectional_tool_continuation_unsupported",
                "provider-native same-stream tool-result continuation is not available for this OpenAI-compatible model",
                retryable=False,
                details={"capability": capability, "tool_call_id": tool_call.get("id") or tool_result.get("tool_call_id")},
            )
        model = {"model_id": self.model_id(), "provider": self.provider_name, "provider_model": self.provider_model(), "continuation_protocol": protocol}
        yield from adapter.continue_with_tool_result(request, model, tool_call, tool_result, stream_context)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--model-instance", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    model_instance = load_json(Path(args.model_instance)) if args.model_instance else {}
    provider = OpenAICompatibleProvider(model_instance, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout)
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
    return 0 if (isinstance(result, list) or result.get("status") == "ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
