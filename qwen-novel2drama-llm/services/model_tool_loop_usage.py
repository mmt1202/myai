from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.cost_estimator import estimate_cost_for_usage, instance_by_id
from services.usage_reconciliation import USAGE_KEYS, normalize_usage, number, provider_actual_usage, usage_has_signal


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def zero_usage() -> dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def add_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    total = zero_usage()
    for key in USAGE_KEYS:
        total[key] = int(number(left.get(key))) + int(number(right.get(key)))
    if not total.get("total_tokens"):
        total["total_tokens"] = total.get("input_tokens", 0) + total.get("output_tokens", 0) + total.get("reasoning_tokens", 0)
    return total


def cost_amount(cost: dict[str, Any] | None) -> float:
    raw = cost or {}
    if raw.get("actual") is not None:
        return number(raw.get("actual"))
    return number(raw.get("estimated"))


def provider_response_model_id(provider_response: dict[str, Any], default_model_id: str | None = None) -> str | None:
    model = provider_response.get("model") or {}
    return model.get("model_id") or provider_response.get("model_id") or provider_response.get("model") or default_model_id


def provider_response_provider(provider_response: dict[str, Any], model_instance: dict[str, Any] | None = None) -> str | None:
    model = provider_response.get("model") or {}
    return model.get("provider") or (model_instance or {}).get("provider")


def cost_for_provider_call(provider_response: dict[str, Any], usage: dict[str, Any], model_instance: dict[str, Any], currency: str) -> dict[str, Any]:
    response_cost = provider_response.get("cost") or {}
    if response_cost and (response_cost.get("actual") is not None or response_cost.get("estimated") is not None):
        amount = cost_amount(response_cost)
        return {
            "currency": response_cost.get("currency") or currency,
            "actual": round(amount, 8),
            "estimated": number(response_cost.get("estimated")),
            "source": "provider_response_cost",
            "pricing_source": response_cost.get("pricing_source"),
        }
    estimated = estimate_cost_for_usage(usage, model_instance, currency=currency) if model_instance else {"estimated": 0.0, "currency": currency, "pricing_source": "unknown"}
    amount = number(estimated.get("estimated"))
    return {
        "currency": estimated.get("currency") or currency,
        "actual": round(amount, 8),
        "estimated": round(amount, 8),
        "source": "estimated_from_usage",
        "pricing_source": estimated.get("pricing_source"),
        "breakdown": estimated.get("breakdown") or {},
    }


def provider_call_record(
    *,
    source: str,
    call_index: int,
    provider_response: dict[str, Any],
    instances_registry: dict[str, Any],
    default_model_id: str | None = None,
) -> dict[str, Any]:
    model_id = provider_response_model_id(provider_response, default_model_id)
    model_instance = instance_by_id(instances_registry, str(model_id)) if model_id else {}
    usage = provider_actual_usage(provider_response)
    usage_source = "provider_response" if usage_has_signal(usage) else "missing_or_zero"
    if usage_source == "missing_or_zero":
        usage = normalize_usage({})
    cost = cost_for_provider_call(provider_response, usage, model_instance, instances_registry.get("default_currency", "USD"))
    return {
        "source": source,
        "call_index": call_index,
        "status": provider_response.get("status"),
        "model_id": model_id,
        "provider": provider_response_provider(provider_response, model_instance),
        "usage_source": usage_source,
        "usage": usage,
        "cost": cost,
    }


def collect_provider_calls(initial_provider_response: dict[str, Any], model_tool_loop_summary: dict[str, Any], *, default_model_id: str | None = None, instances_registry: dict[str, Any]) -> list[dict[str, Any]]:
    calls = [
        provider_call_record(
            source="initial_provider_response",
            call_index=1,
            provider_response=initial_provider_response,
            instances_registry=instances_registry,
            default_model_id=default_model_id,
        )
    ]
    for round_item in model_tool_loop_summary.get("rounds") or []:
        response = round_item.get("provider_response") or {}
        if not response:
            continue
        calls.append(
            provider_call_record(
                source=f"model_tool_loop_round_{round_item.get('round')}",
                call_index=len(calls) + 1,
                provider_response=response,
                instances_registry=instances_registry,
                default_model_id=default_model_id,
            )
        )
    return calls


def aggregate_provider_calls(calls: list[dict[str, Any]], currency: str = "USD") -> dict[str, Any]:
    total_usage = zero_usage()
    actual_cost = 0.0
    estimated_cost = 0.0
    by_model: dict[str, dict[str, Any]] = {}
    by_provider: dict[str, dict[str, Any]] = {}
    missing_usage_sources: list[str] = []
    for call in calls:
        usage = call.get("usage") or {}
        total_usage = add_usage(total_usage, usage)
        cost = call.get("cost") or {}
        actual_cost += number(cost.get("actual"))
        estimated_cost += number(cost.get("estimated"))
        if call.get("usage_source") == "missing_or_zero":
            missing_usage_sources.append(str(call.get("source")))
        for bucket, key in [(by_model, call.get("model_id") or "unknown"), (by_provider, call.get("provider") or "unknown")]:
            item = bucket.setdefault(str(key), {"call_count": 0, "usage": zero_usage(), "actual_cost": 0.0})
            item["call_count"] += 1
            item["usage"] = add_usage(item["usage"], usage)
            item["actual_cost"] = round(number(item.get("actual_cost")) + number(cost.get("actual")), 8)
    warnings = []
    if missing_usage_sources:
        warnings.append("some_provider_calls_missing_usage")
    return {
        "call_count": len(calls),
        "usage": total_usage,
        "cost": {
            "currency": currency,
            "actual": round(actual_cost, 8),
            "estimated": round(estimated_cost, 8),
            "source": "aggregated_provider_calls",
        },
        "by_model": by_model,
        "by_provider": by_provider,
        "warnings": warnings,
        "missing_usage_sources": missing_usage_sources,
    }


def aggregate_model_tool_loop_usage(
    *,
    initial_provider_response: dict[str, Any],
    model_tool_loop_summary: dict[str, Any],
    instances_registry: dict[str, Any],
    selected_model_id: str | None = None,
) -> dict[str, Any]:
    calls = collect_provider_calls(
        initial_provider_response,
        model_tool_loop_summary,
        default_model_id=selected_model_id,
        instances_registry=instances_registry,
    )
    aggregate = aggregate_provider_calls(calls, currency=instances_registry.get("default_currency", "USD"))
    return {
        "status": "ok",
        "selected_model_id": selected_model_id,
        "provider_call_count": aggregate["call_count"],
        "usage": aggregate["usage"],
        "cost": aggregate["cost"],
        "provider_calls": calls,
        "by_model": aggregate["by_model"],
        "by_provider": aggregate["by_provider"],
        "warnings": aggregate["warnings"],
        "missing_usage_sources": aggregate["missing_usage_sources"],
    }


def apply_aggregation_to_provider_response(provider_response: dict[str, Any], aggregation: dict[str, Any]) -> dict[str, Any]:
    provider_response["usage"] = aggregation.get("usage") or {}
    provider_response["cost"] = aggregation.get("cost") or {}
    provider_response["model_tool_loop_usage_aggregation"] = {
        "provider_call_count": aggregation.get("provider_call_count"),
        "warnings": aggregation.get("warnings") or [],
    }
    return provider_response


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate provider usage across model tool-loop rounds.")
    parser.add_argument("--initial-provider-response", required=True)
    parser.add_argument("--model-tool-loop", required=True)
    parser.add_argument("--instances", default="configs/model_instance_registry.json")
    parser.add_argument("--selected-model-id", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = aggregate_model_tool_loop_usage(
        initial_provider_response=load_json(Path(args.initial_provider_response)),
        model_tool_loop_summary=load_json(Path(args.model_tool_loop)),
        instances_registry=load_json(Path(args.instances)),
        selected_model_id=args.selected_model_id,
    )
    if args.output:
        save_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
