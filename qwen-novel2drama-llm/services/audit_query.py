from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_audit_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def query_audit_events(events: list[dict[str, Any]], *, workspace_id: str | None = None, owner_id: str | None = None, decision: str | None = None, since: str | None = None, until: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    since_dt = parse_time(since)
    until_dt = parse_time(until)
    filtered: list[dict[str, Any]] = []
    for event in events:
        if workspace_id and event.get("workspace_id") != workspace_id:
            continue
        if owner_id and event.get("owner_id") != owner_id:
            continue
        if decision and event.get("decision") != decision:
            continue
        event_dt = parse_time(event.get("created_at") or event.get("timestamp"))
        if since_dt and event_dt and event_dt < since_dt:
            continue
        if until_dt and event_dt and event_dt > until_dt:
            continue
        filtered.append(event)
    return filtered[-max(1, int(limit)) :]


def export_audit_jsonl(events: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return {"status": "ok", "path": str(path), "count": len(events)}


def retention_filter(events: list[dict[str, Any]], *, keep_since: str) -> dict[str, Any]:
    keep_dt = parse_time(keep_since)
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for event in events:
        event_dt = parse_time(event.get("created_at") or event.get("timestamp"))
        if keep_dt and event_dt and event_dt < keep_dt:
            dropped.append(event)
        else:
            kept.append(event)
    return {"kept": kept, "dropped_count": len(dropped), "kept_count": len(kept)}
