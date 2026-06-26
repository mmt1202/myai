# P1 Memory Store

The memory store is a foundation service for scoped memory, not a plain chat history file.

Implemented files:

- `configs/schemas/memory_item_schema.json`
- `services/memory_store.py`
- `tests/test_memory_store.py`

## Memory scopes

Supported scopes:

- `session`
- `user`
- `project`
- `task`

Each item can include IDs for:

- `owner_id`
- `project_id`
- `session_id`
- `task_id`

## Memory fields

A memory item includes:

- id
- scope
- content
- summary
- tags
- sensitivity
- retention
- ttl_seconds
- expires_at
- source
- importance
- metadata
- created_at
- updated_at
- deleted_at

## Sensitivity

Supported sensitivity levels:

- `public`
- `internal`
- `confidential`
- `secret`

Search can restrict results with `max_sensitivity`.

## Write memory

```bash
python services/memory_store.py --store outputs/memory/memory.jsonl --write examples/memory_item.json
```

## Search memory

```bash
python services/memory_store.py --store outputs/memory/memory.jsonl --search examples/memory_query.json
```

Query fields:

```json
{
  "scope": "project",
  "project_id": "demo-project",
  "query": "角色设定",
  "tags": ["drama"],
  "max_sensitivity": "internal",
  "limit": 20
}
```

## Delete memory

Delete is soft-delete. The item is kept with `deleted_at` for auditability.

```bash
python services/memory_store.py --store outputs/memory/memory.jsonl --delete mem_xxx
```

## Current limitations

- Storage is JSONL only.
- Search is keyword and tag based.
- No vector retrieval yet.
- No database backend yet.
- No encryption-at-rest layer yet.

## Next steps

- Add hybrid retrieval.
- Add vector index adapter.
- Add database backend.
- Add memory summarization and deduplication.
- Connect memory search/write to the Foundation API routes.
