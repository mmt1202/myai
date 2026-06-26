from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCOPES = {"session", "user", "project", "task"}
SENSITIVITY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    scope = item.get("scope") or "project"
    if scope not in SCOPES:
        raise ValueError(f"unsupported memory scope: {scope}")
    created_at = item.get("created_at") or now_iso()
    ttl_seconds = item.get("ttl_seconds")
    expires_at = item.get("expires_at")
    if ttl_seconds is not None and not expires_at:
        expires_at = (parse_time(created_at) or now_utc() + timedelta(seconds=0)) + timedelta(seconds=int(ttl_seconds))
        expires_at = expires_at.isoformat()
    return {
        "id": item.get("id") or f"mem_{uuid.uuid4().hex}",
        "scope": scope,
        "owner_id": item.get("owner_id"),
        "project_id": item.get("project_id"),
        "session_id": item.get("session_id"),
        "task_id": item.get("task_id"),
        "content": str(item.get("content") or ""),
        "summary": item.get("summary"),
        "tags": list(item.get("tags") or []),
        "sensitivity": item.get("sensitivity") or "internal",
        "retention": item.get("retention") or "project",
        "ttl_seconds": ttl_seconds,
        "expires_at": expires_at,
        "source": item.get("source"),
        "importance": float(item.get("importance") if item.get("importance") is not None else 0.5),
        "metadata": item.get("metadata") or {},
        "created_at": created_at,
        "updated_at": item.get("updated_at") or created_at,
        "deleted_at": item.get("deleted_at"),
    }


def write_memory(path: Path, item: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_item(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return normalized


def read_memory(path: Path, include_deleted: bool = False) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not include_deleted:
        items = [item for item in items if not item.get("deleted_at")]
    return items


def is_expired(item: dict[str, Any], at: datetime | None = None) -> bool:
    expires_at = parse_time(item.get("expires_at"))
    if not expires_at:
        return False
    return expires_at <= (at or now_utc())


def matches_scope(item: dict[str, Any], query: dict[str, Any]) -> bool:
    for key in ["scope", "owner_id", "project_id", "session_id", "task_id"]:
        if query.get(key) and item.get(key) != query.get(key):
            return False
    return True


def matches_sensitivity(item: dict[str, Any], max_sensitivity: str | None) -> bool:
    if not max_sensitivity:
        return True
    item_level = SENSITIVITY_ORDER.get(item.get("sensitivity") or "internal", 1)
    max_level = SENSITIVITY_ORDER.get(max_sensitivity, 1)
    return item_level <= max_level


def search_memory(path: Path, query: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(query.get("query") or "").lower()
    tags = set(query.get("tags") or [])
    limit = int(query.get("limit") or 20)
    max_sensitivity = query.get("max_sensitivity")
    include_expired = bool(query.get("include_expired"))
    results = []
    for item in read_memory(path):
        if not include_expired and is_expired(item):
            continue
        if not matches_scope(item, query):
            continue
        if not matches_sensitivity(item, max_sensitivity):
            continue
        item_tags = set(item.get("tags") or [])
        if tags and not tags.issubset(item_tags):
            continue
        haystack = " ".join([str(item.get("content") or ""), str(item.get("summary") or ""), " ".join(item_tags)]).lower()
        if text and text not in haystack:
            continue
        score = float(item.get("importance") or 0.5)
        if text and text in str(item.get("content") or "").lower():
            score += 0.25
        if tags:
            score += min(0.25, len(tags & item_tags) * 0.05)
        enriched = dict(item)
        enriched["score"] = round(score, 6)
        results.append(enriched)
    results.sort(key=lambda item: (item.get("score", 0), item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return results[:limit]


def delete_memory(path: Path, memory_id: str) -> dict[str, Any] | None:
    items = read_memory(path, include_deleted=True)
    deleted = None
    rewritten = []
    for item in items:
        if item.get("id") == memory_id and not item.get("deleted_at"):
            item = dict(item)
            item["deleted_at"] = now_iso()
            item["updated_at"] = item["deleted_at"]
            deleted = item
        rewritten.append(item)
    if deleted:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rewritten), encoding="utf-8")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="outputs/memory/memory.jsonl")
    parser.add_argument("--write", default=None)
    parser.add_argument("--search", default=None)
    parser.add_argument("--delete", default=None)
    parser.add_argument("--include-deleted", action="store_true")
    args = parser.parse_args()
    path = Path(args.store)
    if args.write:
        item = json.loads(Path(args.write).read_text(encoding="utf-8"))
        result = {"item": write_memory(path, item)}
    elif args.search:
        query = json.loads(Path(args.search).read_text(encoding="utf-8"))
        result = {"items": search_memory(path, query)}
    elif args.delete:
        result = {"deleted": delete_memory(path, args.delete)}
    else:
        result = {"items": read_memory(path, include_deleted=args.include_deleted)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
