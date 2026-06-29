from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.postgres_migration_history import MigrationConflictError, apply_migration_with_history, migration_checksum, migration_plan


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn
        self.last_select_id: str | None = None
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        normalized = " ".join(sql.lower().split())
        self.executed.append((sql, params))
        self.conn.executed.append(sql)
        if normalized.startswith("select checksum"):
            self.last_select_id = str(params[0]) if params else None
        elif normalized.startswith("insert into schema_migrations") and params:
            migration_id = str(params[0])
            self.conn.rows[migration_id] = {"checksum": params[1], "statement_count": params[2], "applied_at": params[3]}

    def fetchone(self) -> dict[str, Any] | None:
        if self.last_select_id is None:
            return None
        return self.conn.rows.get(self.last_select_id)


class FakeConn:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.executed: list[str] = []
        self.commit_count = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commit_count += 1


class PostgresMigrationHistoryTests(unittest.TestCase):
    def test_migration_checksum_is_stable(self) -> None:
        self.assertEqual(migration_checksum("SELECT 1;\n"), migration_checksum("SELECT 1;"))
        self.assertNotEqual(migration_checksum("SELECT 1;"), migration_checksum("SELECT 2;"))

    def test_migration_plan_reads_file_and_counts_statements(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "demo.sql"
            path.write_text("CREATE TABLE demo(id TEXT);\nCREATE INDEX demo_idx ON demo(id);\n", encoding="utf-8")
            plan = migration_plan(path)
            self.assertEqual(plan["migration_id"], "demo")
            self.assertEqual(plan["statement_count"], 2)
            self.assertEqual(plan["history_table"], "schema_migrations")
            self.assertEqual(plan["sql_path"], str(path))

    def test_apply_migration_records_history_and_is_idempotent(self) -> None:
        conn = FakeConn()
        sql = "CREATE TABLE demo(id TEXT);"
        first = apply_migration_with_history(conn, sql=sql, migration_id="demo", metadata={"source": "test"})
        self.assertEqual(first["status"], "applied")
        self.assertIn("demo", conn.rows)
        second = apply_migration_with_history(conn, sql=sql, migration_id="demo", metadata={"source": "test"})
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual(second["checksum"], first["checksum"])
        self.assertGreaterEqual(conn.commit_count, 2)

    def test_apply_migration_detects_checksum_conflict(self) -> None:
        conn = FakeConn()
        apply_migration_with_history(conn, sql="CREATE TABLE demo(id TEXT);", migration_id="demo")
        with self.assertRaises(MigrationConflictError):
            apply_migration_with_history(conn, sql="CREATE TABLE demo(id INTEGER);", migration_id="demo")


if __name__ == "__main__":
    unittest.main()
