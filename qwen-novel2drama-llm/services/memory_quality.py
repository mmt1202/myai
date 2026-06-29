from __future__ import annotations

from collections import defaultdict
from typing import Any


def norm(value: str) -> str:
    return " ".join(value.lower().strip().split())


def duplicate_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        scope_key = str(item.get("project_id") or item.get("owner_id") or item.get("session_id") or item.get("task_id") or "default")
        groups[(str(item.get("scope") or "project"), scope_key, norm(str(item.get("content") or "")))].append(item)
    return [{"memory_ids": [item.get("id") for item in group], "count": len(group)} for group in groups.values() if len(group) > 1]


def conflict_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        subject = str((item.get("metadata") or {}).get("subject") or "")
        if subject:
            grouped[subject].append(item)
    issues = []
    for subject, group in grouped.items():
        labels = {str((item.get("metadata") or {}).get("label") or "unknown") for item in group}
        if "yes" in labels and "no" in labels:
            issues.append({"subject": subject, "memory_ids": [item.get("id") for item in group], "labels": sorted(labels)})
    return issues


def merge_group(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        raise ValueError("items required")
    selected = sorted(items, key=lambda item: float(item.get("importance") or 0.5), reverse=True)[0]
    merged = dict(selected)
    merged["tags"] = sorted({tag for item in items for tag in (item.get("tags") or [])})
    merged["importance"] = max(float(item.get("importance") or 0.5) for item in items)
    merged["metadata"] = {**(merged.get("metadata") or {}), "merged_from": [item.get("id") for item in items]}
    return merged


def compress_items(items: list[dict[str, Any]], *, max_items: int = 5) -> dict[str, Any]:
    ranked = sorted(items, key=lambda item: float(item.get("importance") or 0.5), reverse=True)[:max_items]
    return {"summary": "；".join(str(item.get("summary") or item.get("content") or "") for item in ranked), "source_count": len(items), "used_count": len(ranked), "memory_ids": [item.get("id") for item in ranked]}


def quality_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    duplicates = duplicate_groups(items)
    conflicts = conflict_groups(items)
    return {"status": "review" if duplicates or conflicts else "ok", "duplicate_count": len(duplicates), "conflict_count": len(conflicts), "duplicates": duplicates, "conflicts": conflicts}
