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
