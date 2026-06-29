# Memory Roadmap

The Foundation memory layer now supports selectable backends while preserving the stable `/v1/memory/write` and `/v1/memory/search` API shapes.

## Implemented backends

### File / JSONL backend

`services/memory_store.py` provides JSONL-backed scoped memory:

- scopes: session, user, project, task
- tags
- sensitivity
- ttl / expiry
- importance
- keyword-style query filtering
- append-only write path
- soft delete by rewrite

### SQLite backend

`services/sqlite_memory_store.py` provides `SQLiteMemoryStore`:

- `memories` table
- scope/owner/project/session/task fields
- JSON tags column
- JSON metadata column
- TTL / expiry filtering
- sensitivity filtering
- soft delete
- indexed scope and timestamp fields

### Vector backend

`services/vector_memory_store.py` provides `VectorMemoryStore`:

- deterministic hash embedding provider for dependency-free CI
- vector score
- lexical score
- hybrid result score
- JSONL persistence compatibility

This vector backend is intentionally local and deterministic. A real embedding provider can replace `HashEmbeddingProvider` later without changing the memory API shape.

## Backend selection

Use environment variables:

```text
FOUNDATION_MEMORY_BACKEND=file|sqlite|vector
FOUNDATION_MEMORY_STORE=outputs/memory/memory.jsonl
FOUNDATION_MEMORY_DB=outputs/memory/memory.sqlite
```

Factory entrypoints:

```text
services.memory_store:build_memory_store
services.memory_store:memory_store_from_env
```

## API integration

`inference/api_server.py` now uses `memory_store_from_env(project_root=PROJECT_ROOT)` for:

```text
POST /v1/memory/write
POST /v1/memory/search
```

Readiness also reports `memory_backend` metadata.

## Stable memory result shape

Memory search results keep this shape, with backend-specific optional fields allowed:

```json
{
  "id": "...",
  "scope": "project",
  "content": "...",
  "tags": [],
  "importance": 0.5,
  "score": 1.0,
  "metadata": {}
}
```

Vector backend may add:

```json
{
  "lexical_score": 0.75,
  "vector_score": 0.42
}
```

## Tests

```bash
python -m unittest tests.test_memory_store tests.test_sqlite_memory_store tests.test_vector_memory_store tests.test_memory_backend_selection tests.test_memory_api_backend
```

## Still planned

Future memory work:

- external embedding provider integration
- persistent vector index backend
- duplicate detection
- contradiction detection
- merge policy
- source confidence
- stale memory archival
- memory compression
