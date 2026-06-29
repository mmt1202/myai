from __future__ import annotations

from typing import Any


CONTENT_MODALITY_MAP = {
    "text": "text",
    "subtitle": "text",
    "reasoning_hint": "text",
    "tool_result": "text",
    "image": "image",
    "audio": "audio",
    "video": "video",
    "file": "file",
    "url": "file",
}


def infer_input_modalities(request: dict[str, Any]) -> set[str]:
    blocks = request.get("input") or request.get("messages") or []
    modalities: set[str] = set()
    if isinstance(blocks, str):
        return {"text"}
    if isinstance(blocks, dict):
        blocks = [blocks]
    for item in blocks if isinstance(blocks, list) else []:
        if not isinstance(item, dict):
            modalities.add("text")
            continue
        block_type = str(item.get("type") or "text")
        modalities.add(CONTENT_MODALITY_MAP.get(block_type, block_type))
    return modalities or {"text"}


def requested_output_modality(request: dict[str, Any]) -> str:
    return str(request.get("output_modality") or request.get("response_modality") or "text")


def provider_supports_modalities(instance: dict[str, Any], input_modalities: set[str], output_modality: str) -> bool:
    inputs = set(instance.get("input_modalities") or [])
    outputs = set(instance.get("output_modalities") or [])
    return input_modalities.issubset(inputs) and output_modality in outputs


def multimodal_candidates(registry: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    input_modalities = infer_input_modalities(request)
    output_modality = requested_output_modality(request)
    return [item for item in registry.get("instances", []) if provider_supports_modalities(item, input_modalities, output_modality)]


def multimodal_route_plan(registry: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    input_modalities = sorted(infer_input_modalities(request))
    output_modality = requested_output_modality(request)
    candidates = multimodal_candidates(registry, request)
    return {"input_modalities": input_modalities, "output_modality": output_modality, "candidate_count": len(candidates), "candidates": candidates, "selected_model_id": candidates[0].get("id") if candidates else None}


def normalize_multimodal_block(block: dict[str, Any]) -> dict[str, Any]:
    block_type = str(block.get("type") or "text")
    modality = CONTENT_MODALITY_MAP.get(block_type, block_type)
    return {"type": block_type, "modality": modality, "uri": block.get("uri"), "file_id": block.get("file_id"), "text": block.get("text"), "metadata": block.get("metadata") or {}}
