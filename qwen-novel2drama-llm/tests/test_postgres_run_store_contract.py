from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.postgres_run_store import POSTGRES_RUN_STORE_REQUIRED_TABLES, POSTGRES_RUN_STORE_SCHEMA_SQL, PostgresRunStore, PostgresRunStoreUnavailable
from agent.run_store import build_run_store


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

    def test_build_run_store_selects_real_postgres_implementation(self) -> None:
        store = build_run_store("postgres", PROJECT_ROOT / "outputs" / "test", postgres_dsn="configured")
        self.assertIsInstance(store, PostgresRunStore)
        metadata = store.metadata()
        self.assertEqual(metadata["type"], "postgres")
        self.assertEqual(metadata["implementation_status"], "persistence_v1")
        self.assertTrue(metadata["dsn_configured"])

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


if __name__ == "__main__":
    unittest.main()
