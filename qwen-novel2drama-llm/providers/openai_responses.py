from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator

from providers.base import BaseProvider, ProviderError, normalize_usage, output_text_block, provider_stream_event, response_envelope


RESPONSES_PATH = "/responses"
GENERIC_API_KEY_ENV = "MODEL_API_KEY"


class OpenAIResponsesProvider(BaseProvider):
    provider_name = "openai_responses"

    def __init__(self, model_instance: dict[str, Any] | None = None, *, base_url: str | None = None, api_key_env: str | None = None, timeout: int = 120) -> None:
        super().__init__(model_instance=model_instance)
        runtime_config = self.model_instance.get("runtime_config") or {}
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        configured_api_key_env = runtime_config.get("api_key_env") or "OPENAI_API_KEY"
        self.api_key_env = configured_api_key_env if api_key_env in {None, GENERIC_API_KEY_ENV} else api_key_env
        self.model_name_env = runtime_config.get("model_name_env") or "OPENAI_MODEL"
        self.timeout = timeout

    def provider_model(self) -> str:
        configured = os.environ.get(self.model_name_env)
        if configured:
            return configured
        model_name = str(self.model_instance.get("model_name") or "")
        if model_name.startswith("${") and model_name.endswith("}"):
            return self.model_id()
        return model_name or self.model_id()

    def request_headers(self) -> dict[str, str]:
        api_key = os.environ.get(self.api_key_env)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def is_dry_run(self, request: dict[str, Any]) -> bool:
        return bool(request.get("dry_run") or request.get("dry_run_provider"))

    def input_content_block(self, block: dict[str, Any]) -> dict[str, Any] | None:
        block_type = str(block.get("type") or "text")
        if block_type in {"text", "subtitle", "reasoning_hint", "tool_result", "metadata"}:
            if block_type == "metadata":
                text = json.dumps(block.get("metadata") or {}, ensure_ascii=False)
            else:
                text = str(block.get("text") or "")
            return {"type": "input_text", "text": text}
        if block_type == "image":
            payload: dict[str, Any] = {"type": "input_image", "detail": block.get("detail") or "auto"}
            if block.get("file_id"):
                payload["file_id"] = str(block["file_id"])
            else:
                payload["image_url"] = str(block.get("image_url") or block.get("uri") or block.get("url") or "")
            return payload
        if block_type in {"file", "url"}:
            payload = {"type": "input_file", "detail": block.get("detail") or "low"}
            if block.get("file_id"):
                payload["file_id"] = str(block["file_id"])
            elif block.get("file_data"):
                payload["file_data"] = str(block["file_data"])
            else:
                payload["file_url"] = str(block.get("file_url") or block.get("uri") or block.get("url") or "")
            if block.get("filename"):
                payload["filename"] = str(block["filename"])
            return payload
        if block_type in {"audio", "video"}:
            return {"type": "input_text", "text": f"[{block_type}: {block.get('uri') or block.get('file_id') or block.get('filename') or 'inline'}]"}
        return None

    def build_input(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if request.get("system"):
            items.append({"role": "system", "content": str(request["system"]), "type": "message"})
        if request.get("developer"):
            items.append({"role": "developer", "content": str(request["developer"]), "type": "message"})
        content = []
        for block in request.get("input") or []:
            mapped = self.input_content_block(block)
            if mapped:
                content.append(mapped)
        if not content:
            content.append({"type": "input_text", "text": str(request.get("task") or request.get("prompt") or "")})
        items.append({"role": "user", "content": content, "type": "message"})
        return items

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": request.get("model") or self.provider_model(), "input": self.build_input(request)}
        if request.get("instructions"):
            payload["instructions"] = str(request["instructions"])
        if request.get("max_output_tokens") is not None:
            payload["max_output_tokens"] = int(request["max_output_tokens"])
        if request.get("temperature") is not None:
            payload["temperature"] = float(request["temperature"])
        if request.get("tools"):
            payload["tools"] = request["tools"]
        if request.get("tool_choice"):
            payload["tool_choice"] = request["tool_choice"]
        if request.get("response_format"):
            payload["text"] = {"format": request["response_format"]}
        if request.get("metadata"):
            payload["metadata"] = request["metadata"]
        if request.get("store") is not None:
            payload["store"] = bool(request["store"])
        if request.get("stream"):
            payload["stream"] = True
            if request.get("stream_options"):
                payload["stream_options"] = request["stream_options"]
            elif request.get("stream_include_obfuscation") is not None:
                payload["stream_options"] = {"include_obfuscation": bool(request["stream_include_obfuscation"])}
        return payload

    def build_http_request(self, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(f"{self.base_url}{RESPONSES_PATH}", data=json.dumps(payload).encode("utf-8"), headers=self.request_headers(), method="POST")

    def extract_output_text(self, data: dict[str, Any]) -> str:
        if data.get("output_text") is not None:
            return str(data.get("output_text") or "")
        parts: list[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                    parts.append(str(content.get("text") or ""))
        return "".join(parts)

    def parse_response(self, data: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        usage = normalize_usage(data.get("usage") or {})
        text = self.extract_output_text(data)
        return response_envelope(
            status="ok",
            output={"content": [output_text_block(text)], "raw_response_id": data.get("id"), "raw_status": data.get("status"), "raw_output": data.get("output") or []},
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
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}{RESPONSES_PATH}"},
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": payload["model"]},
                warnings=["dry_run_no_provider_call"],
            )
        if not os.environ.get(self.api_key_env):
            raise ProviderError("provider_auth_missing", f"missing API key env: {self.api_key_env}", retryable=False)
        try:
            with urllib.request.urlopen(self.build_http_request(payload), timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        return self.parse_response(data, request)

    def iter_sse_json(self, response: Any) -> Iterator[dict[str, Any]]:
        event_name: str | None = None
        data_lines: list[str] = []
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line)
            line = line.rstrip("\r\n")
            if not line:
                if data_lines:
                    text = "\n".join(data_lines)
                    data_lines = []
                    if text == "[DONE]":
                        return
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise ProviderError("provider_error", f"invalid provider stream chunk: {text}", details={"line": text}) from exc
                    if event_name and isinstance(payload, dict) and not payload.get("type"):
                        payload["type"] = event_name
                    event_name = None
                    yield payload
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if data_lines:
            text = "\n".join(data_lines)
            if text != "[DONE]":
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ProviderError("provider_error", f"invalid provider stream chunk: {text}", details={"line": text}) from exc
                if event_name and isinstance(payload, dict) and not payload.get("type"):
                    payload["type"] = event_name
                yield payload

    def stream_delta_from_event(self, data: dict[str, Any]) -> str:
        for key in ("delta", "text"):
            if data.get(key) is not None:
                return str(data.get(key) or "")
        if isinstance(data.get("item"), dict):
            item = data["item"]
            if item.get("type") in {"output_text", "text"} and item.get("text") is not None:
                return str(item.get("text") or "")
        return ""

    def stream_usage_from_event(self, data: dict[str, Any]) -> dict[str, Any]:
        response = data.get("response") if isinstance(data.get("response"), dict) else data
        usage = response.get("usage") if isinstance(response, dict) else None
        return normalize_usage(usage or {}) if usage else {}

    def stream_output_from_completed_event(self, data: dict[str, Any], collected: list[str]) -> dict[str, Any]:
        response = data.get("response") if isinstance(data.get("response"), dict) else data
        text = self.extract_output_text(response if isinstance(response, dict) else {}) or "".join(collected)
        output: dict[str, Any] = {"content": [output_text_block(text)], "raw_event_type": data.get("type")}
        if isinstance(response, dict):
            output["raw_response_id"] = response.get("id")
            output["raw_status"] = response.get("status")
            output["raw_output"] = response.get("output") or []
        return output

    def is_terminal_stream_event(self, data: dict[str, Any]) -> bool:
        event_type = str(data.get("type") or "")
        return event_type.endswith("completed") or event_type in {"response.completed", "response.done"}

    def is_error_stream_event(self, data: dict[str, Any]) -> bool:
        event_type = str(data.get("type") or "")
        return event_type.endswith("failed") or event_type.endswith("error") or event_type in {"error", "response.failed", "response.error"}

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
            metadata={"provider": self.provider_name, "url": f"{self.base_url}{RESPONSES_PATH}", "native_stream": True},
        )
        if self.is_dry_run(request):
            yield provider_stream_event(
                "provider_stream_delta",
                request_id_value=request_id_value,
                trace_id=trace_id,
                model=model_info,
                delta=json.dumps({"dry_run": True, "provider_payload": payload}, ensure_ascii=False),
                index=0,
                metadata={"dry_run": True, "native_stream": True},
            )
            yield provider_stream_event(
                "provider_stream_completed",
                request_id_value=request_id_value,
                trace_id=trace_id,
                model=model_info,
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}{RESPONSES_PATH}"},
                done=True,
                metadata={"dry_run": True, "native_stream": True},
            )
            return
        if not os.environ.get(self.api_key_env):
            raise ProviderError("provider_auth_missing", f"missing API key env: {self.api_key_env}", retryable=False)
        collected: list[str] = []
        usage: dict[str, Any] = {}
        completed_output: dict[str, Any] | None = None
        try:
            with urllib.request.urlopen(self.build_http_request(payload), timeout=self.timeout) as response:
                for data in self.iter_sse_json(response):
                    event_type = str(data.get("type") or "response.event")
                    if self.is_error_stream_event(data):
                        error = data.get("error") if isinstance(data.get("error"), dict) else {"message": data.get("message") or event_type}
                        raise ProviderError("provider_error", str(error.get("message") or event_type), retryable=False, details={"event": data})
                    event_usage = self.stream_usage_from_event(data)
                    if event_usage:
                        usage = event_usage
                    delta = self.stream_delta_from_event(data)
                    if delta:
                        collected.append(delta)
                        yield provider_stream_event(
                            "provider_stream_delta",
                            request_id_value=request_id_value,
                            trace_id=trace_id,
                            model=model_info,
                            delta=delta,
                            index=len(collected) - 1,
                            metadata={"raw_event_type": event_type, "raw_event_id": data.get("id")},
                        )
                    elif event_type and not self.is_terminal_stream_event(data):
                        yield provider_stream_event(
                            "provider_stream_event",
                            request_id_value=request_id_value,
                            trace_id=trace_id,
                            model=model_info,
                            metadata={"raw_event_type": event_type, "raw_event": data},
                        )
                    if self.is_terminal_stream_event(data):
                        completed_output = self.stream_output_from_completed_event(data, collected)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        output = completed_output or {"content": [output_text_block("".join(collected))]}
        yield provider_stream_event(
            "provider_stream_completed",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            output=output,
            usage=usage,
            done=True,
            metadata={"native_stream": True, "collected_delta_count": len(collected)},
        )


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
    provider = OpenAIResponsesProvider(model_instance, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout)
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
    status = result[-1].get("event_type") if isinstance(result, list) and result else result.get("status", "ok")
    return 0 if status in {"ok", "provider_stream_completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
