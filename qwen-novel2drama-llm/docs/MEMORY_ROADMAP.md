# Memory Roadmap

The current Foundation memory store is intentionally simple and dependency-free.

## Current implementation

`services/memory_store.py` provides JSONL-backed scoped memory:

- scopes: session, user, project, task
- tags
- sensitivity
- ttl / expiry
- importance
- keyword-style query filtering
- append-only write path

This is suitable for local development and deterministic CI.

## Stable memory result shape

Memory search results should keep this shape:

```json
{
  "memory_id": "...",
  "scope": "project",
  "content": "...",
  "tags": [],
  "importance": 0.5,
  "score": 1.0,
  "metadata": {}
}
```

## Next storage backends

### SQLite memory store

Planned features:

- `memories` table
- indexed scope/project/user/task fields
- tags table or JSON column
- soft delete
- deterministic migration script

### Vector memory

Planned features:

- embedding provider interface
- vector index abstraction
- hybrid keyword + vector search
- reranking
- memory compression

## Conflict and update policy

Future memory updates should define:

- duplicate detection
- contradiction detection
- merge policy
- source confidence
- stale memory archival

## Boundary

Memory roadmap does not require changing the current `/v1/memory/search` and `/v1/memory/write` API shapes. Future backends should preserve the current response envelope and item shape.
