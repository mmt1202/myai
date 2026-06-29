from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from agent.postgres_run_store import load_schema_sql, split_sql_statements
from agent.runtime import now_iso

MIGRATION_HISTORY_TABLE = "schema_migrations"

MIGRATION_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    statement_count INTEGER NOT NULL,
    applied_at TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
"""


class MigrationConflictError(RuntimeError):
    pass


def migration_checksum(sql: str) -> str:
    normalized = "\n".join(line.rstrip() for line in sql.strip().splitlines()) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def default_migration_id(sql_path: Path | str) -> str:
    return Path(sql_path).stem


def migration_plan(sql_path: Path | str, *, migration_id: str | None = None) -> dict[str, Any]:
    path = Path(sql_path)
    sql = load_schema_sql(path)
    statements = split_sql_statements(sql)
    return {
        "migration_id": migration_id or default_migration_id(path),
        "sql_path": str(path),
        "checksum": migration_checksum(sql),
        "statement_count": len(statements),
        "statements": [statement.splitlines()[0].strip() for statement in statements],
        "history_table": MIGRATION_HISTORY_TABLE,
    }


def ensure_history_table(cur: Any) -> None:
    for statement in split_sql_statements(MIGRATION_HISTORY_SQL):
        cur.execute(statement)


def apply_migration_with_history(conn: Any, *, sql: str, migration_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    checksum = migration_checksum(sql)
    statements = split_sql_statements(sql)
    with conn.cursor() as cur:
        ensure_history_table(cur)
        cur.execute("SELECT checksum, statement_count, applied_at FROM schema_migrations WHERE migration_id = %s", (migration_id,))
        row = cur.fetchone()
        if row is not None:
            current_checksum = row["checksum"] if isinstance(row, dict) else row[0]
            if current_checksum != checksum:
                raise MigrationConflictError(f"migration {migration_id} already applied with a different checksum")
            conn.commit()
            return {"status": "already_applied", "migration_id": migration_id, "checksum": checksum, "statement_count": int(row["statement_count"] if isinstance(row, dict) else row[1]), "applied_at": row["applied_at"] if isinstance(row, dict) else row[2]}
        for statement in statements:
            cur.execute(statement)
        cur.execute(
            "INSERT INTO schema_migrations(migration_id, checksum, statement_count, applied_at, metadata_json) VALUES(%s, %s, %s, %s, %s::jsonb)",
            (migration_id, checksum, len(statements), now_iso(), __import__("json").dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
        )
    conn.commit()
    return {"status": "applied", "migration_id": migration_id, "checksum": checksum, "statement_count": len(statements)}
