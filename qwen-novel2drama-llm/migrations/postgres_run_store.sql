-- Postgres Agent Run Store schema v1.
-- This migration mirrors the RunStore contract used by FileRunStore and SQLiteRunStore.

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    statement_count INTEGER NOT NULL,
    applied_at TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS run_requests (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    request_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS run_reports (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    report_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    event_type TEXT,
    status TEXT,
    created_at TEXT NOT NULL,
    event_json JSONB NOT NULL,
    PRIMARY KEY(run_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_created ON run_events(run_id, created_at, event_id);

CREATE TABLE IF NOT EXISTS cancel_requests (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    marker_json JSONB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT,
    artifact_json JSONB NOT NULL,
    PRIMARY KEY(run_id, name)
);

CREATE TABLE IF NOT EXISTS run_leases (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL,
    lease_json JSONB NOT NULL,
    lease_expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_leases_status_expires ON run_leases(status, lease_expires_at);
