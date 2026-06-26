from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from token_counter import estimate_request_usage


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def instance_by_id(registry: dict[str, Any], model_id: str) -> dict[str, Any]:
    for item in registry.get("instances", []):
        if item.get("id") == model_id or model_id in item.get("aliases", []):
            return item
    raise KeyError(f"model instance not found: {model_id}")


def safe_number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def estimate_cost_for_usage(usage: dict[str, Any], model_instance: dict[str, Any], currency: str = "USD") -> dict[str, Any]:
    cost_config = model_instance.get("cost") or {}
    input_per_1m = safe_number(cost_config.get("input_per_1m"))
    output_per_1m = safe_number(cost_config.get("output_per_1m"))
    image_unit = safe_number(cost_config.get("image_unit"))
    video_second = safe_number(cost_config.get("video_second"))
    audio_second = safe_number(cost_config.get("audio_second"))
    input_cost = usage.get("input_tokens", 0) / 1_000_000 * input_per_1m
    output_cost = usage.get("output_tokens", 0) / 1_000_000 * output_per_1m
    image_cost = usage.get("image_units", 0) * image_unit
    video_cost = usage.get("video_seconds", 0) * video_second
    audio_cost = usage.get("audio_seconds", 0) * audio_second
    total = input_cost + output_cost + image_cost + video_cost + audio_cost
    return {
        "currency": currency,
        "estimated": round(total, 8),
        "actual": None,
        "breakdown": {
            "input_tokens": round(input_cost, 8),
            "output_tokens": round(output_cost, 8),
            "image_units": round(image_cost, 8),
            "video_seconds": round(video_cost, 8),
            "audio_seconds": round(audio_cost, 8),
        },
        "pricing_source": model_instance.get("id"),
        "notes": cost_config.get("notes"),
    }


def estimate_request_cost(request: dict[str, Any], model_instance: dict[str, Any], expected_output_tokens: int = 512, currency: str = "USD") -> dict[str, Any]:
    usage = estimate_request_usage(request, expected_output_tokens=expected_output_tokens)
    cost = estimate_cost_for_usage(usage, model_instance, currency=currency)
    return {"usage": usage, "cost": cost, "model": {"model_id": model_instance.get("id"), "provider": model_instance.get("provider")}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--instances", default="configs/model_instance_registry.json")
    parser.add_argument("--expected-output-tokens", type=int, default=512)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    registry = load_json(Path(args.instances))
    model_instance = instance_by_id(registry, args.model_id)
    report = estimate_request_cost(request, model_instance, expected_output_tokens=args.expected_output_tokens, currency=registry.get("default_currency", "USD"))
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
