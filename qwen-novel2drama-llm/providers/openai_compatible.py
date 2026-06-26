from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator

from providers.base import BaseProvider, ProviderError, normalize_usage, output_text_block, provider_stream_event, response_envelope, text_from_content_blocks


class OpenAICompatibleProvider(BaseProvider):
    provider_name = "openai_compatible"

    def __init__(self, model_instance: dict[str, Any] | None = None, *, base_url: str | None = None, api_key_env: str = "MODEL_API_KEY", timeout: int = 120) -> None:
        super().__init__(model_instance=model_instance)
        self.base_url = (base_url or os.environ.get("MODEL_BASE_URL") or "http://localhost:8000/v1").rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout

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
        if request.get("dry_run"):
            return response_envelope(
                status="ok",
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}/chat/completions"},
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": payload["model"]},
                warnings=["dry_run_no_provider_call"],
            )
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

    def stream_finish_reason(self, data: dict[str, Any]) -> str | None:
        choices = data.get("choices") or []
        if not choices:
            return None
        value = choices[0].get("finish_reason")
        return str(value) if value else None

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
            metadata={"provider": self.provider_name, "url": f"{self.base_url}/chat/completions"},
        )
        if request.get("dry_run"):
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
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}/chat/completions"},
                done=True,
                metadata={"dry_run": True},
            )
            return
        http_request = self.build_http_request(payload)
        collected: list[str] = []
        usage: dict[str, Any] = {}
        finish_reason: str | None = None
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                for index, data in enumerate(self.iter_sse_json(response)):
                    if data.get("usage"):
                        usage = normalize_usage(data.get("usage") or {})
                    reason = self.stream_finish_reason(data)
                    if reason:
                        finish_reason = reason
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
        yield provider_stream_event(
            "provider_stream_completed",
            request_id_value=request_id_value,
            trace_id=trace_id,
            model=model_info,
            output={"content": [output_text_block(text)], "finish_reason": finish_reason},
            usage=usage,
            done=True,
            metadata={"native_stream": True},
        )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--model-instance", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    if args.stream:
        request["stream"] = True
    instance = load_json(Path(args.model_instance)) if args.model_instance else {}
    provider = OpenAICompatibleProvider(instance, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout)
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
