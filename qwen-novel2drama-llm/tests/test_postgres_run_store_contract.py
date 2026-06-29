from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.postgres_run_store import (
    POSTGRES_RUN_STORE_REQUIRED_TABLES,
    POSTGRES_RUN_STORE_SCHEMA_SQL,
    PostgresConnectionProfile,
    PostgresRunStore,
    PostgresRunStoreUnavailable,
    load_schema_sql,
    split_sql_statements,
)
from agent.run_store import build_run_store
from scripts.apply_postgres_run_store_migration import migration_plan


class PostgresRunStoreContractTests(unittest.TestCase):
    def test_schema_contains_required_tables_and_indexes(self) -> None:
        normalized = POSTGRES_RUN_STORE_SCHEMA_SQL.lower()
        for table in POSTGRES_RUN_STORE_REQUIRED_TABLES:
            self.assertIn(f"create table if not exists {table}", normalized)
        self.assertIn("jsonb", normalized)
        self.assertIn("idx_run_events_run_created", normalized)
        self.assertIn("idx_run_leases_status_expires", normalized)

    def test_migration_file_matches_required_contract_surface(self) -> None:
        migration = (PROJECT_ROOT / "migrations" / "postgres_run_store.sql").read_text(encoding="utf-8").lower()
        for table in POSTGRES_RUN_STORE_REQUIRED_TABLES:
            self.assertIn(f"create table if not exists {table}", migration)
        self.assertIn("jsonb", migration)
        self.assertIn("run_leases", migration)

    def test_split_sql_statements_handles_semicolons_in_strings(self) -> None:
        statements = split_sql_statements("SELECT ';' AS value; CREATE TABLE demo(id TEXT);")
        self.assertEqual(len(statements), 2)
        self.assertIn("SELECT ';'", statements[0])
        self.assertIn("CREATE TABLE demo", statements[1])

    def test_migration_plan_reports_statement_count_without_dsn(self) -> None:
        plan = migration_plan(PROJECT_ROOT / "migrations" / "postgres_run_store.sql")
        self.assertGreaterEqual(plan["statement_count"], len(POSTGRES_RUN_STORE_REQUIRED_TABLES))
        self.assertEqual(plan["sql_path"], str(PROJECT_ROOT / "migrations" / "postgres_run_store.sql"))

    def test_load_schema_sql_defaults_and_path(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS runs", load_schema_sql())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schema.sql"
            path.write_text("SELECT 1;", encoding="utf-8")
            self.assertEqual(load_schema_sql(path), "SELECT 1;")

    def test_connection_profile_normalizes_values_and_reads_env(self) -> None:
        old_values = {key: os.environ.get(key) for key in [
            "FOUNDATION_AGENT_RUN_POSTGRES_POOL_ENABLED",
            "FOUNDATION_AGENT_RUN_POSTGRES_POOL_MIN",
            "FOUNDATION_AGENT_RUN_POSTGRES_POOL_MAX",
            "FOUNDATION_AGENT_RUN_POSTGRES_POOL_TIMEOUT",
        ]}
        os.environ["FOUNDATION_AGENT_RUN_POSTGRES_POOL_ENABLED"] = "true"
        os.environ["FOUNDATION_AGENT_RUN_POSTGRES_POOL_MIN"] = "3"
        os.environ["FOUNDATION_AGENT_RUN_POSTGRES_POOL_MAX"] = "2"
        os.environ["FOUNDATION_AGENT_RUN_POSTGRES_POOL_TIMEOUT"] = "0"
        try:
            profile = PostgresConnectionProfile.from_env().normalized()
            self.assertTrue(profile.pool_enabled)
            self.assertEqual(profile.pool_min_size, 3)
            self.assertEqual(profile.pool_max_size, 3)
            self.assertEqual(profile.pool_timeout, 1.0)
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_build_run_store_selects_real_postgres_implementation(self) -> None:
        store = build_run_store("postgres", PROJECT_ROOT / "outputs" / "test", postgres_dsn="configured")
        self.assertIsInstance(store, PostgresRunStore)
        metadata = store.metadata()
        self.assertEqual(metadata["type"], "postgres")
        self.assertEqual(metadata["implementation_status"], "persistence_v1")
        self.assertTrue(metadata["dsn_configured"])
        self.assertIn("connection_profile", metadata)

    def test_safe_run_id_and_artifact_paths_do_not_connect(self) -> None:
        store = PostgresRunStore("configured", output_root=PROJECT_ROOT / "outputs" / "postgres-test")
        self.assertEqual(store.safe_run_id("demo"), "demo")
        self.assertEqual(store.artifact_path("demo", "events.jsonl"), PROJECT_ROOT / "outputs" / "postgres-test" / "demo" / "events.jsonl")
        for value in ["", "../x", "a/b", "a\\b"]:
            with self.assertRaises(ValueError):
                store.safe_run_id(value)

    def test_missing_dsn_fails_explicitly_on_runtime_operation(self) -> None:
        old = os.environ.pop("FOUNDATION_AGENT_RUN_POSTGRES_DSN", None)
        try:
            store = PostgresRunStore(output_root=PROJECT_ROOT / "outputs" / "postgres-test")
            self.assertFalse(store.metadata()["dsn_configured"])
            with self.assertRaises(PostgresRunStoreUnavailable):
                store.list_runs()
        finally:
            if old is not None:
                os.environ["FOUNDATION_AGENT_RUN_POSTGRES_DSN"] = old

    def test_optional_real_database_contract(self) -> None:
        dsn = os.environ.get("FOUNDATION_AGENT_RUN_POSTGRES_DSN")
        if not dsn:
            self.skipTest("FOUNDATION_AGENT_RUN_POSTGRES_DSN not configured")
        store = PostgresRunStore(dsn, output_root=PROJECT_ROOT / "outputs" / "postgres-test", connect=True, auto_init=True)
        run_id = "postgres_contract_demo"
        request = {"run_id": run_id, "task": "postgres contract", "owner_id": "tester", "status": "created"}
        report = {"run_id": run_id, "task": "postgres contract", "status": "completed", "owner_id": "tester", "artifacts": {}}
        store.save_request(run_id, request)
        store.save_report(run_id, report)
        store.append_event(run_id, {"event_type": "run_completed", "status": "completed"})
        store.save_artifact(run_id, "usage.json", {"tokens": 3})
        self.assertEqual(store.load_request(run_id)["task"], "postgres contract")
        self.assertEqual(store.load_report(run_id)["status"], "completed")
        self.assertGreaterEqual(len(store.load_events(run_id)), 1)
        self.assertEqual(store.status(run_id)["status"], "completed")
        self.assertGreaterEqual(store.list_runs(query="postgres contract")["total"], 1)
        claim = store.claim_run(run_id, "worker-a", lease_seconds=30)
        self.assertTrue(claim["claimed"])
        self.assertTrue(store.renew_lease(run_id, "worker-a", lease_seconds=30)["renewed"])
        self.assertTrue(store.release_run(run_id, "worker-a")["released"])
        store.close()


if __name__ == "__main__":
    unittest.main()
