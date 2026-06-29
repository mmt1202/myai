from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    started_at: str
    ended_at: str | None = None
    parent_span_id: str | None = None
    attributes: dict[str, Any] | None = None
    status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attributes"] = self.attributes or {}
        return data


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex}"


def new_span_id() -> str:
    return f"span_{uuid.uuid4().hex}"


def start_span(name: str, *, trace_id: str | None = None, parent_span_id: str | None = None, attributes: dict[str, Any] | None = None) -> TraceSpan:
    return TraceSpan(trace_id=trace_id or new_trace_id(), span_id=new_span_id(), name=name, parent_span_id=parent_span_id, started_at=now_iso(), attributes=attributes or {})


def finish_span(span: TraceSpan, *, status: str = "ok", attributes: dict[str, Any] | None = None) -> TraceSpan:
    return TraceSpan(trace_id=span.trace_id, span_id=span.span_id, name=span.name, parent_span_id=span.parent_span_id, started_at=span.started_at, ended_at=now_iso(), attributes={**(span.attributes or {}), **(attributes or {})}, status=status)


def append_span(path: Path, span: TraceSpan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(span.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def load_spans(path: Path, *, trace_id: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    spans: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if trace_id and item.get("trace_id") != trace_id:
            continue
        spans.append(item)
    return spans


def trace_summary(spans: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_name: dict[str, int] = {}
    for span in spans:
        by_status[str(span.get("status") or "unknown")] = by_status.get(str(span.get("status") or "unknown"), 0) + 1
        by_name[str(span.get("name") or "unknown")] = by_name.get(str(span.get("name") or "unknown"), 0) + 1
    return {"span_count": len(spans), "by_status": by_status, "by_name": by_name}
