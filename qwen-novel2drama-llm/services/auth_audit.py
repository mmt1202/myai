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
        "event_type": event.get("event_type") or "auth",
        "decision": event.get("decision") or "unknown",
        "key_id": event.get("key_id"),
        "owner_id": event.get("owner_id"),
        "workspace_id": event.get("workspace_id"),
        "required_scope": event.get("required_scope"),
        "method": event.get("method"),
        "path": event.get("path"),
        "status_code": event.get("status_code"),
        "reason": event.get("reason"),
        "client_host": event.get("client_host"),
        "metadata": event.get("metadata") or {},
    }


def write_auth_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_event(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n")
    return normalized


def read_auth_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def summarize_auth_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_decision: dict[str, int] = {}
    by_key: dict[str, int] = {}
    by_scope: dict[str, int] = {}
    for event in events:
        decision = str(event.get("decision") or "unknown")
        key_id = str(event.get("key_id") or "anonymous")
        scope = str(event.get("required_scope") or "public")
        by_decision[decision] = by_decision.get(decision, 0) + 1
        by_key[key_id] = by_key.get(key_id, 0) + 1
        by_scope[scope] = by_scope.get(scope, 0) + 1
    return {"event_count": len(events), "by_decision": by_decision, "by_key": by_key, "by_scope": by_scope}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="outputs/auth/auth_audit.jsonl")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    events = read_auth_events(Path(args.log))
    if args.summary:
        print(json.dumps(summarize_auth_events(events), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
