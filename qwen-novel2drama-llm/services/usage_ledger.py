from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": event.get("created_at") or now_iso(),
        "request_id": event.get("request_id"),
        "trace_id": event.get("trace_id"),
        "model_id": event.get("model_id"),
        "provider": event.get("provider"),
        "route_mode": event.get("route_mode"),
        "usage": event.get("usage") or {},
        "cost": event.get("cost") or {},
        "status": event.get("status") or "estimated",
    }


def write_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return normalized


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "event_count": len(events),
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "actual_cost": 0.0,
        "by_model": {},
        "by_provider": {},
    }
    for event in events:
        usage = event.get("usage") or {}
        cost = event.get("cost") or {}
        for key in ["input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"]:
            summary[key] += int(usage.get(key) or 0)
        summary["estimated_cost"] += float(cost.get("estimated") or 0)
        summary["actual_cost"] += float(cost.get("actual") or 0)
        for bucket_name, field in [("by_model", "model_id"), ("by_provider", "provider")]:
            name = event.get(field) or "unknown"
            bucket = summary[bucket_name].setdefault(name, {"event_count": 0, "total_tokens": 0, "estimated_cost": 0.0, "actual_cost": 0.0})
            bucket["event_count"] += 1
            bucket["total_tokens"] += int(usage.get("total_tokens") or 0)
            bucket["estimated_cost"] += float(cost.get("estimated") or 0)
            bucket["actual_cost"] += float(cost.get("actual") or 0)
    summary["estimated_cost"] = round(summary["estimated_cost"], 8)
    summary["actual_cost"] = round(summary["actual_cost"], 8)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="outputs/usage/usage_ledger.jsonl")
    parser.add_argument("--event", default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    path = Path(args.ledger)
    if args.event:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        result = {"event": write_event(path, event)}
    else:
        events = read_events(path)
        result = {"summary": summarize(events)} if args.summary else {"summary": summarize(events), "events": events}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
