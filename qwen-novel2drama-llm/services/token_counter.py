from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_CHARS_PER_TOKEN = 4
CJK_CHARS_PER_TOKEN = 1.7


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_cjk_heavy(text: str) -> bool:
    if not text:
        return False
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk_count / max(len(text), 1) > 0.25


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    divisor = CJK_CHARS_PER_TOKEN if is_cjk_heavy(text) else DEFAULT_CHARS_PER_TOKEN
    return max(1, math.ceil(len(text) / divisor))


def estimate_image_units(block: dict[str, Any]) -> float:
    width = int(block.get("width") or 1024)
    height = int(block.get("height") or 1024)
    megapixels = (width * height) / 1_000_000
    return max(1.0, round(megapixels, 3))


def estimate_content_block(block: dict[str, Any]) -> dict[str, Any]:
    block_type = block.get("type")
    result = {
        "type": block_type,
        "input_tokens": 0,
        "image_units": 0.0,
        "video_seconds": 0.0,
        "audio_seconds": 0.0,
    }
    if block_type in {"text", "subtitle", "reasoning_hint", "tool_result"}:
        result["input_tokens"] = estimate_text_tokens(str(block.get("text") or ""))
    elif block_type == "metadata":
        result["input_tokens"] = estimate_text_tokens(json.dumps(block.get("metadata") or {}, ensure_ascii=False))
    elif block_type == "image":
        result["image_units"] = estimate_image_units(block)
        result["input_tokens"] = math.ceil(result["image_units"] * 256)
    elif block_type == "video":
        duration_ms = int(block.get("duration_ms") or 0)
        seconds = duration_ms / 1000 if duration_ms else 0
        result["video_seconds"] = seconds
        result["input_tokens"] = math.ceil(seconds * 64)
    elif block_type == "audio":
        duration_ms = int(block.get("duration_ms") or 0)
        seconds = duration_ms / 1000 if duration_ms else 0
        result["audio_seconds"] = seconds
        result["input_tokens"] = math.ceil(seconds * 16)
    elif block_type in {"file", "url"}:
        result["input_tokens"] = estimate_text_tokens(str(block.get("uri") or block.get("filename") or block.get("file_id") or ""))
    return result


def estimate_request_usage(request: dict[str, Any], expected_output_tokens: int = 512) -> dict[str, Any]:
    blocks = request.get("input") or []
    block_estimates = [estimate_content_block(block) for block in blocks]
    input_tokens = sum(item["input_tokens"] for item in block_estimates)
    image_units = sum(item["image_units"] for item in block_estimates)
    video_seconds = sum(item["video_seconds"] for item in block_estimates)
    audio_seconds = sum(item["audio_seconds"] for item in block_estimates)
    memory_tokens = estimate_text_tokens(json.dumps(request.get("memory") or {}, ensure_ascii=False))
    rules_tokens = estimate_text_tokens(json.dumps(request.get("rules") or {}, ensure_ascii=False))
    total_input = input_tokens + memory_tokens + rules_tokens
    return {
        "input_tokens": total_input,
        "output_tokens": expected_output_tokens,
        "reasoning_tokens": int(request.get("expected_reasoning_tokens") or 0),
        "cached_input_tokens": int(request.get("cached_input_tokens") or 0),
        "image_units": image_units,
        "video_seconds": video_seconds,
        "audio_seconds": audio_seconds,
        "total_tokens": total_input + expected_output_tokens + int(request.get("expected_reasoning_tokens") or 0),
        "block_estimates": block_estimates,
        "estimator": "heuristic_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--expected-output-tokens", type=int, default=512)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    usage = estimate_request_usage(request, expected_output_tokens=args.expected_output_tokens)
    text = json.dumps(usage, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
