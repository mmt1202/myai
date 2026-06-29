-- Postgres quota store schema v1.
-- Persists rate-limit buckets, workspace usage counters, and quota events.

CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    window_start INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_usage (
    workspace_id TEXT NOT NULL,
    period_key TEXT NOT NULL,
    usage_json JSONB NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, period_key)
);

CREATE INDEX IF NOT EXISTS idx_workspace_usage_workspace_period ON workspace_usage(workspace_id, period_key);

CREATE TABLE IF NOT EXISTS workspace_quota_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    event_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workspace_quota_events_workspace_created ON workspace_quota_events(workspace_id, created_at, id);
