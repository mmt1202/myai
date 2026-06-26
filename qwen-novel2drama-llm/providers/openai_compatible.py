from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from providers.base import BaseProvider, ProviderError, normalize_usage, output_text_block, response_envelope, text_from_content_blocks


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
        return payload

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
        payload = self.build_payload(request)
        if request.get("dry_run"):
            return response_envelope(
                status="ok",
                output={"dry_run": True, "provider_payload": payload, "url": f"{self.base_url}/chat/completions"},
                request_id_value=request.get("request_id"),
                trace_id=request.get("trace_id"),
                model={"model_id": self.model_id(), "provider": self.provider_name, "provider_model": payload["model"]},
                warnings=["dry_run_no_provider_call"],
            )
        api_key = os.environ.get(self.api_key_env)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError("provider_error", f"HTTP {exc.code}: {body}", retryable=exc.code >= 500, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            raise ProviderError("provider_unavailable", str(exc), retryable=True) from exc
        return self.parse_chat_response(data, request)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--model-instance", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    instance = load_json(Path(args.model_instance)) if args.model_instance else {}
    provider = OpenAICompatibleProvider(instance, base_url=args.base_url, api_key_env=args.api_key_env, timeout=args.timeout)
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
