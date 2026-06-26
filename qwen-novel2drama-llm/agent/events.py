from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id") or new_event_id(),
        "created_at": event.get("created_at") or now_iso(),
        "run_id": event.get("run_id"),
        "session_id": event.get("session_id"),
        "owner_id": event.get("owner_id"),
        "project_id": event.get("project_id"),
        "event_type": event.get("event_type") or "agent_event",
        "status": event.get("status"),
        "step_id": event.get("step_id"),
        "step_type": event.get("step_type"),
        "message": event.get("message"),
        "data": event.get("data") or {},
        "error": event.get("error"),
    }


def write_agent_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_event(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n")
    return normalized


def read_agent_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def summarize_agent_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    terminal_event: dict[str, Any] | None = None
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        status = str(event.get("status") or "unknown")
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        if event_type in {"run_completed", "run_failed", "run_cancelled", "run_waiting_approval"}:
            terminal_event = event
    return {
        "event_count": len(events),
        "by_type": by_type,
        "by_status": by_status,
        "first_event": events[0] if events else None,
        "last_event": events[-1] if events else None,
        "terminal_event": terminal_event,
    }


class AgentEventWriter:
    def __init__(self, path: Path, run: dict[str, Any] | None = None, *, enabled: bool = True) -> None:
        self.path = path
        self.run = run or {}
        self.enabled = enabled

    def context(self) -> dict[str, Any]:
        return {
            "run_id": self.run.get("run_id"),
            "session_id": self.run.get("session_id"),
            "owner_id": self.run.get("owner_id"),
            "project_id": self.run.get("project_id"),
        }

    def emit(
        self,
        event_type: str,
        *,
        status: str | None = None,
        step: dict[str, Any] | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        step = step or {}
        return write_agent_event(
            self.path,
            {
                **self.context(),
                "event_type": event_type,
                "status": status,
                "step_id": step.get("step_id"),
                "step_type": step.get("type"),
                "message": message,
                "data": data or {},
                "error": error,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="outputs/agent_runtime/run/events.jsonl")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    events = read_agent_events(Path(args.events))
    if args.summary:
        print(json.dumps(summarize_agent_events(events), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
