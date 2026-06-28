from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.cost_estimator import estimate_cost_for_usage, instance_by_id

USAGE_KEYS = [
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cached_input_tokens",
    "total_tokens",
    "image_units",
    "video_seconds",
    "audio_seconds",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def int_number(value: Any) -> int:
    return int(number(value))


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    raw = usage or {}
    normalized = {key: int_number(raw.get(key)) for key in USAGE_KEYS}
    if not normalized["input_tokens"]:
        normalized["input_tokens"] = int_number(raw.get("prompt_tokens"))
    if not normalized["output_tokens"]:
        normalized["output_tokens"] = int_number(raw.get("completion_tokens"))
    if not normalized["total_tokens"]:
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"] + normalized["reasoning_tokens"]
    return normalized


def usage_delta(estimated: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in USAGE_KEYS:
        estimated_value = int_number(estimated.get(key))
        actual_value = int_number(actual.get(key))
        difference = actual_value - estimated_value
        ratio = None if estimated_value == 0 else round(actual_value / estimated_value, 6)
        delta[key] = {"estimated": estimated_value, "actual": actual_value, "delta": difference, "ratio": ratio}
    return delta


def cost_amount(cost: dict[str, Any] | None, key: str) -> float:
    return number((cost or {}).get(key))


def reconcile_cost(estimated_cost: dict[str, Any] | None, actual_usage: dict[str, Any], model_instance: dict[str, Any], currency: str = "USD") -> dict[str, Any]:
    estimated = estimated_cost or {}
    actual_cost_estimate = estimate_cost_for_usage(actual_usage, model_instance, currency=currency)
    actual_amount = cost_amount(actual_cost_estimate, "estimated")
    estimated_amount = cost_amount(estimated, "estimated")
    delta = actual_amount - estimated_amount
    ratio = None if estimated_amount == 0 else round(actual_amount / estimated_amount, 6)
    return {
        "currency": estimated.get("currency") or actual_cost_estimate.get("currency") or currency,
        "estimated": estimated_amount,
        "actual": round(actual_amount, 8),
        "delta": round(delta, 8),
        "ratio": ratio,
        "estimated_cost": estimated,
        "actual_cost": {**actual_cost_estimate, "actual": round(actual_amount, 8)},
        "pricing_source": actual_cost_estimate.get("pricing_source"),
    }


def provider_actual_usage(provider_response: dict[str, Any] | None) -> dict[str, Any]:
    response = provider_response or {}
    usage = response.get("usage") or {}
    if usage:
        return normalize_usage(usage)
    stream = response.get("stream") or {}
    stream_usage = stream.get("usage") if isinstance(stream, dict) else None
    if isinstance(stream_usage, dict):
        return normalize_usage(stream_usage)
    return normalize_usage({})


def usage_has_signal(usage: dict[str, Any]) -> bool:
    return any(int_number(usage.get(key)) > 0 for key in USAGE_KEYS)


def reconcile_provider_usage(
    *,
    request_id: str | None,
    trace_id: str | None,
    route_decision: dict[str, Any],
    provider_response: dict[str, Any] | None,
    instances_registry: dict[str, Any],
) -> dict[str, Any]:
    selected_model_id = route_decision.get("selected_model_id") or (((provider_response or {}).get("model") or {}).get("model_id"))
    selected = route_decision.get("selected") or {}
    provider = selected.get("provider") or (((provider_response or {}).get("model") or {}).get("provider"))
    estimated_usage = normalize_usage(route_decision.get("estimated_usage") or {})
    actual_usage = provider_actual_usage(provider_response)
    warnings: list[str] = []
    if not usage_has_signal(actual_usage):
        warnings.append("provider_actual_usage_missing_or_zero")
        actual_usage = estimated_usage
        usage_source = "estimated_fallback"
    else:
        usage_source = "provider_response"
    model_instance = instance_by_id(instances_registry, str(selected_model_id)) if selected_model_id else {}
    cost = reconcile_cost(selected.get("estimated_cost") or {}, actual_usage, model_instance, currency=instances_registry.get("default_currency", "USD")) if model_instance else {}
    total_delta = usage_delta(estimated_usage, actual_usage).get("total_tokens", {})
    status = "ok" if usage_source == "provider_response" else "fallback"
    return {
        "request_id": request_id,
        "trace_id": trace_id,
        "status": status,
        "model_id": selected_model_id,
        "provider": provider,
        "usage_source": usage_source,
        "usage": {
            "estimated": estimated_usage,
            "actual": actual_usage,
            "delta": usage_delta(estimated_usage, actual_usage),
        },
        "cost": cost,
        "summary": {
            "estimated_total_tokens": estimated_usage.get("total_tokens", 0),
            "actual_total_tokens": actual_usage.get("total_tokens", 0),
            "total_token_delta": total_delta.get("delta", 0),
            "total_token_ratio": total_delta.get("ratio"),
            "estimated_cost": cost.get("estimated"),
            "actual_cost": cost.get("actual"),
            "cost_delta": cost.get("delta"),
            "cost_ratio": cost.get("ratio"),
        },
        "warnings": warnings,
    }


def reconciled_usage(report: dict[str, Any]) -> dict[str, Any]:
    return ((report.get("usage") or {}).get("actual") or {})


def reconciled_cost(report: dict[str, Any]) -> dict[str, Any]:
    cost = report.get("cost") or {}
    return {
        "currency": cost.get("currency"),
        "estimated": cost.get("estimated"),
        "actual": cost.get("actual"),
        "delta": cost.get("delta"),
        "ratio": cost.get("ratio"),
        "pricing_source": cost.get("pricing_source"),
        "breakdown": ((cost.get("actual_cost") or {}).get("breakdown") or {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile routed estimated usage/cost with provider actual usage/cost.")
    parser.add_argument("--route-decision", required=True)
    parser.add_argument("--provider-response", required=True)
    parser.add_argument("--instances", default="configs/model_instance_registry.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    route_decision = load_json(Path(args.route_decision))
    provider_response = load_json(Path(args.provider_response))
    instances = load_json(Path(args.instances))
    report = reconcile_provider_usage(
        request_id=provider_response.get("request_id") or route_decision.get("request_id"),
        trace_id=provider_response.get("trace_id") or route_decision.get("trace_id"),
        route_decision=route_decision,
        provider_response=provider_response,
        instances_registry=instances,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
