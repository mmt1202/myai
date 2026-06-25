from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_prompt(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_openai_compatible_request(prompt_payload: dict[str, Any], model: str, temperature: float = 0.0) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": "You generate patch_spec_v1 JSON only. No markdown. No prose.",
            },
            {
                "role": "user",
                "content": compact_prompt(prompt_payload),
            },
        ],
    }


def build_local_generate_request(prompt_payload: dict[str, Any], temperature: float = 0.0) -> dict[str, Any]:
    return {
        "prompt": compact_prompt(prompt_payload),
        "temperature": temperature,
    }


def post_json(url: str, payload: dict[str, Any], api_key: str | None = None, timeout: int = 120) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"model API returned HTTP {exc.code}: {body}") from exc


def extract_openai_compatible_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("response message content is not a string")
    return content.strip()


def extract_local_generate_text(response: dict[str, Any]) -> str:
    for key in ("result", "text", "content", "response"):
        value = response.get(key)
        if isinstance(value, str):
            return value.strip()
    raise ValueError("local generate response does not contain result/text/content/response")


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def call_model(prompt_payload: dict[str, Any], mode: str, url: str, model: str, api_key: str | None, temperature: float, timeout: int) -> dict[str, Any]:
    if mode == "openai_compatible":
        request_payload = build_openai_compatible_request(prompt_payload, model, temperature)
        response = post_json(url, request_payload, api_key=api_key, timeout=timeout)
        return parse_json_text(extract_openai_compatible_text(response))
    if mode == "local_generate":
        request_payload = build_local_generate_request(prompt_payload, temperature)
        response = post_json(url, request_payload, api_key=api_key, timeout=timeout)
        return parse_json_text(extract_local_generate_text(response))
    raise ValueError(f"unsupported mode: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", default="outputs/model_outputs/patch_spec.json")
    parser.add_argument("--mode", choices=["openai_compatible", "local_generate"], default="openai_compatible")
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", default="local-model")
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt_payload = load_json(Path(args.prompt))
    api_key = os.environ.get(args.api_key_env)

    if args.dry_run:
        request_payload = (
            build_openai_compatible_request(prompt_payload, args.model, args.temperature)
            if args.mode == "openai_compatible"
            else build_local_generate_request(prompt_payload, args.temperature)
        )
        print(json.dumps({"mode": args.mode, "url": args.url, "request": request_payload}, ensure_ascii=False, indent=2))
        return 0

    patch_spec = call_model(prompt_payload, args.mode, args.url, args.model, api_key, args.temperature, args.timeout)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(patch_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"model patch spec written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
