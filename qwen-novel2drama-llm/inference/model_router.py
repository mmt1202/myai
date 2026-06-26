from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.token_counter import estimate_request_usage
from services.cost_estimator import estimate_cost_for_usage

ROUTE_MODE_WEIGHTS: dict[str, dict[str, float]] = {
    "smart": {"quality": 0.55, "capability_match": 0.25, "latency": 0.10, "cost": 0.05, "privacy": 0.05},
    "cheap": {"cost": 0.60, "capability_match": 0.25, "latency": 0.10, "quality": 0.05},
    "balanced": {"quality": 0.35, "cost": 0.25, "capability_match": 0.25, "latency": 0.10, "privacy": 0.05},
    "local_first": {"privacy": 0.35, "cost": 0.25, "capability_match": 0.25, "quality": 0.10, "latency": 0.05},
    "cloud_first": {"quality": 0.50, "capability_match": 0.25, "latency": 0.15, "cost": 0.10},
    "drama_specialist": {"drama_relevance": 0.45, "quality": 0.25, "capability_match": 0.20, "cost": 0.05, "latency": 0.05},
    "code_specialist": {"capability_match": 0.40, "quality": 0.30, "latency": 0.15, "cost": 0.10, "privacy": 0.05},
}

DRAMA_CAPABILITIES = {"drama.story_reasoning", "drama.visual_planning"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def content_modalities(request: dict[str, Any]) -> set[str]:
    modalities = set()
    for block in request.get("input") or []:
        block_type = block.get("type")
        if block_type:
            modalities.add(str(block_type))
    return modalities or {"text"}


def normalize_required_capabilities(request: dict[str, Any], route_mode: str) -> set[str]:
    required = set(request.get("required_capabilities") or [])
    if not required:
        required.add("text.chat")
    if route_mode == "drama_specialist":
        required.add("text.reason")
    if route_mode == "code_specialist":
        required.add("tool.calling")
    return required


def rejects_reason(instance: dict[str, Any], request: dict[str, Any], usage: dict[str, Any], required_capabilities: set[str], required_modalities: set[str]) -> str | None:
    capabilities = set(instance.get("capabilities") or [])
    if not required_capabilities.issubset(capabilities):
        return "missing_capability"
    input_modalities = set(instance.get("input_modalities") or [])
    required_for_model = {"file" if item == "url" else item for item in required_modalities}
    if "metadata" in required_for_model:
        required_for_model.remove("metadata")
        required_for_model.add("text")
    if not required_for_model.issubset(input_modalities):
        return "missing_modality"
    privacy = request.get("privacy") or {}
    if privacy.get("local_only") and instance.get("provider") != "local":
        return "privacy_boundary"
    context_window = instance.get("context_window")
    if isinstance(context_window, int) and context_window > 0 and usage.get("total_tokens", 0) > context_window:
        return "context_window_exceeded"
    if instance.get("lifecycle") == "deprecated" and not request.get("allow_deprecated"):
        return "deprecated_model"
    return None


def value_cost_score(instance: dict[str, Any]) -> float:
    cost = instance.get("cost") or {}
    values = [value for key, value in cost.items() if isinstance(value, (int, float)) and key.endswith("per_1m")]
    if not values:
        return 1.0 if instance.get("provider") == "local" else 0.5
    average = sum(values) / len(values)
    return max(0.0, min(1.0, 1.0 / (1.0 + average)))


def capability_match_score(instance: dict[str, Any], required_capabilities: set[str]) -> float:
    capabilities = set(instance.get("capabilities") or [])
    if not required_capabilities:
        return 1.0
    return len(required_capabilities & capabilities) / len(required_capabilities)


def quality_score(instance: dict[str, Any]) -> float:
    aliases = set(instance.get("aliases") or [])
    if "frontier" in aliases or "smart" in aliases:
        return 0.95
    if instance.get("provider") == "local":
        return 0.55
    if "cheap" in aliases or "bulk" in aliases:
        return 0.45
    return 0.65


def latency_score(instance: dict[str, Any]) -> float:
    if instance.get("provider") == "local":
        return 0.8
    return 0.55


def privacy_score(instance: dict[str, Any]) -> float:
    privacy = instance.get("privacy") or {}
    return 1.0 if privacy.get("data_leaves_device") is False else 0.35


def drama_relevance_score(instance: dict[str, Any]) -> float:
    capabilities = set(instance.get("capabilities") or [])
    if capabilities & DRAMA_CAPABILITIES:
        return 1.0
    if "text.reason" in capabilities or "vision.understand" in capabilities:
        return 0.65
    return 0.25


def score_instance(instance: dict[str, Any], route_mode: str, required_capabilities: set[str]) -> dict[str, Any]:
    metrics = {
        "quality": quality_score(instance),
        "cost": value_cost_score(instance),
        "capability_match": capability_match_score(instance, required_capabilities),
        "latency": latency_score(instance),
        "privacy": privacy_score(instance),
        "drama_relevance": drama_relevance_score(instance),
    }
    weights = ROUTE_MODE_WEIGHTS.get(route_mode, ROUTE_MODE_WEIGHTS["balanced"])
    total = sum(metrics[key] * weight for key, weight in weights.items())
    return {"score": round(total, 6), "metrics": metrics, "weights": weights}


def route_model(request: dict[str, Any], instances_registry: dict[str, Any]) -> dict[str, Any]:
    route_mode = request.get("route_mode") or "balanced"
    expected_output_tokens = int(request.get("expected_output_tokens") or 512)
    usage = estimate_request_usage(request, expected_output_tokens=expected_output_tokens)
    required_capabilities = normalize_required_capabilities(request, route_mode)
    required_modalities = content_modalities(request)
    candidates = []
    rejected = []
    for instance in instances_registry.get("instances", []):
        reason = rejects_reason(instance, request, usage, required_capabilities, required_modalities)
        if reason:
            rejected.append({"model_id": instance.get("id"), "reason": reason})
            continue
        score = score_instance(instance, route_mode, required_capabilities)
        cost = estimate_cost_for_usage(usage, instance, instances_registry.get("default_currency", "USD"))
        candidates.append({"model_id": instance.get("id"), "provider": instance.get("provider"), "score": score["score"], "score_detail": score, "estimated_cost": cost})
    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected = candidates[0] if candidates else None
    return {
        "request_id": request.get("request_id"),
        "trace_id": request.get("trace_id"),
        "route_mode": route_mode,
        "required_capabilities": sorted(required_capabilities),
        "required_modalities": sorted(required_modalities),
        "candidate_model_ids": [item["model_id"] for item in candidates],
        "rejected_candidates": rejected,
        "selected_model_id": selected.get("model_id") if selected else None,
        "selected": selected,
        "fallback_chain": [item["model_id"] for item in candidates[1:4]],
        "estimated_usage": usage,
        "policy_hits": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "routed" if selected else "no_candidate",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--instances", default="configs/model_instance_registry.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    registry = load_json(Path(args.instances))
    result = route_model(request, registry)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "routed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
