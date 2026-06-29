from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from services.memory_store import is_expired, matches_scope, matches_sensitivity, normalize_item, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  owner_id TEXT,
  project_id TEXT,
  session_id TEXT,
  task_id TEXT,
  content TEXT NOT NULL,
  summary TEXT,
  tags_json TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  retention TEXT,
  ttl_seconds INTEGER,
  expires_at TEXT,
  source TEXT,
  importance REAL NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope, owner_id, project_id, session_id, task_id);
CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at);
CREATE INDEX IF NOT EXISTS idx_memories_deleted ON memories(deleted_at);
"""


class SQLiteMemoryStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def metadata(self) -> dict[str, Any]:
        return {"type": "sqlite", "db_path": str(self.db_path)}

    def write(self, item: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_item(item)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                  id, scope, owner_id, project_id, session_id, task_id, content, summary, tags_json,
                  sensitivity, retention, ttl_seconds, expires_at, source, importance, metadata_json,
                  created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["id"],
                    normalized["scope"],
                    normalized.get("owner_id"),
                    normalized.get("project_id"),
                    normalized.get("session_id"),
                    normalized.get("task_id"),
                    normalized.get("content") or "",
                    normalized.get("summary"),
                    json.dumps(normalized.get("tags") or [], ensure_ascii=False),
                    normalized.get("sensitivity") or "internal",
                    normalized.get("retention"),
                    normalized.get("ttl_seconds"),
                    normalized.get("expires_at"),
                    normalized.get("source"),
                    float(normalized.get("importance") or 0.5),
                    json.dumps(normalized.get("metadata") or {}, ensure_ascii=False),
                    normalized.get("created_at"),
                    normalized.get("updated_at"),
                    normalized.get("deleted_at"),
                ),
            )
            conn.commit()
        return normalized

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "scope": row["scope"],
            "owner_id": row["owner_id"],
            "project_id": row["project_id"],
            "session_id": row["session_id"],
            "task_id": row["task_id"],
            "content": row["content"],
            "summary": row["summary"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "sensitivity": row["sensitivity"],
            "retention": row["retention"],
            "ttl_seconds": row["ttl_seconds"],
            "expires_at": row["expires_at"],
            "source": row["source"],
            "importance": float(row["importance"] or 0.5),
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "deleted_at": row["deleted_at"],
        }

    def read(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memories"
        params: list[Any] = []
        if not include_deleted:
            sql += " WHERE deleted_at IS NULL"
        sql += " ORDER BY updated_at DESC, created_at DESC"
        with self._connect() as conn:
            return [self._row_to_item(row) for row in conn.execute(sql, params).fetchall()]

    def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        text = str(query.get("query") or "").lower()
        tags = set(query.get("tags") or [])
        limit = int(query.get("limit") or 20)
        max_sensitivity = query.get("max_sensitivity")
        include_expired = bool(query.get("include_expired"))
        results: list[dict[str, Any]] = []
        for item in self.read():
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

    def delete(self, memory_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ? AND deleted_at IS NULL", (memory_id,)).fetchone()
            if not row:
                return None
            deleted = self._row_to_item(row)
            deleted_at = now_iso()
            conn.execute("UPDATE memories SET deleted_at = ?, updated_at = ? WHERE id = ?", (deleted_at, deleted_at, memory_id))
            conn.commit()
            deleted["deleted_at"] = deleted_at
            deleted["updated_at"] = deleted_at
            return deleted
