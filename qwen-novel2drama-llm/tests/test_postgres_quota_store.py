from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.postgres_quota_store import (  # noqa: E402
    DEFAULT_POSTGRES_QUOTA_DSN_ENV,
    POSTGRES_QUOTA_REQUIRED_TABLES,
    POSTGRES_QUOTA_SCHEMA_SQL,
    PostgresQuotaStore,
    PostgresQuotaStoreUnavailable,
    load_schema_sql,
    split_sql_statements,
)
from services.quota_store import build_quota_store, quota_backend_from_env, quota_store_from_env  # noqa: E402
from services.workspace_quota import record_workspace_usage_to_path  # noqa: E402


class PostgresQuotaStoreContractTests(unittest.TestCase):
    def test_schema_contains_required_tables_and_indexes(self) -> None:
        normalized = POSTGRES_QUOTA_SCHEMA_SQL.lower()
        for table in POSTGRES_QUOTA_REQUIRED_TABLES:
            self.assertIn(f"create table if not exists {table}", normalized)
        self.assertIn("jsonb", normalized)
        self.assertIn("idx_workspace_usage_workspace_period", normalized)
        self.assertIn("idx_workspace_quota_events_workspace_created", normalized)

    def test_migration_file_matches_required_contract_surface(self) -> None:
        migration = (PROJECT_ROOT / "migrations" / "postgres_quota_store.sql").read_text(encoding="utf-8").lower()
        for table in POSTGRES_QUOTA_REQUIRED_TABLES:
            self.assertIn(f"create table if not exists {table}", migration)
        self.assertIn("jsonb", migration)
        self.assertIn("workspace_quota_events", migration)

    def test_split_sql_statements_handles_semicolons_in_strings(self) -> None:
        statements = split_sql_statements("SELECT ';' AS value; CREATE TABLE demo(id TEXT);")
        self.assertEqual(len(statements), 2)
        self.assertIn("SELECT ';'", statements[0])
        self.assertIn("CREATE TABLE demo", statements[1])

    def test_load_schema_sql_defaults_and_path(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS rate_limit_buckets", load_schema_sql())
        path = PROJECT_ROOT / "outputs" / "postgres_quota_schema_test.sql"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SELECT 1;", encoding="utf-8")
        self.assertEqual(load_schema_sql(path), "SELECT 1;")

    def test_build_quota_store_selects_postgres_aliases_without_connecting(self) -> None:
        for kind in ["postgres", "postgresql", "pg"]:
            store = build_quota_store(kind, rate_limit_state_path=PROJECT_ROOT / "outputs" / "rate.json", workspace_quota_state_path=PROJECT_ROOT / "outputs" / "quota.json", postgres_dsn="configured")
            self.assertIsInstance(store, PostgresQuotaStore)
            self.assertEqual(store.metadata()["type"], "postgres")
            self.assertTrue(store.metadata()["dsn_configured"])

    def test_env_backend_and_dsn_are_supported_without_connecting(self) -> None:
        old_backend = os.environ.get("FOUNDATION_QUOTA_BACKEND")
        old_dsn = os.environ.get(DEFAULT_POSTGRES_QUOTA_DSN_ENV)
        os.environ["FOUNDATION_QUOTA_BACKEND"] = "postgres"
        os.environ[DEFAULT_POSTGRES_QUOTA_DSN_ENV] = "configured"
        try:
            self.assertEqual(quota_backend_from_env(), "postgres")
            store = quota_store_from_env(rate_limit_state_path=PROJECT_ROOT / "outputs" / "rate.json", workspace_quota_state_path=PROJECT_ROOT / "outputs" / "quota.json")
            self.assertIsInstance(store, PostgresQuotaStore)
            self.assertTrue(store.metadata()["dsn_configured"])
        finally:
            if old_backend is None:
                os.environ.pop("FOUNDATION_QUOTA_BACKEND", None)
            else:
                os.environ["FOUNDATION_QUOTA_BACKEND"] = old_backend
            if old_dsn is None:
                os.environ.pop(DEFAULT_POSTGRES_QUOTA_DSN_ENV, None)
            else:
                os.environ[DEFAULT_POSTGRES_QUOTA_DSN_ENV] = old_dsn

    def test_missing_dsn_fails_explicitly_on_runtime_operation(self) -> None:
        old = os.environ.pop(DEFAULT_POSTGRES_QUOTA_DSN_ENV, None)
        try:
            store = PostgresQuotaStore()
            self.assertFalse(store.metadata()["dsn_configured"])
            with self.assertRaises(PostgresQuotaStoreUnavailable):
                store.workspace_current_usage(workspace_id="w1", period_key="daily:2026-06-28", usage_keys=["requests"])
        finally:
            if old is not None:
                os.environ[DEFAULT_POSTGRES_QUOTA_DSN_ENV] = old

    def test_optional_real_database_contract(self) -> None:
        dsn = os.environ.get(DEFAULT_POSTGRES_QUOTA_DSN_ENV)
        if not dsn:
            self.skipTest(f"{DEFAULT_POSTGRES_QUOTA_DSN_ENV} not configured")
        store = PostgresQuotaStore(dsn, connect=True, auto_init=True)
        bucket = "postgres-quota-contract|model:invoke|w1"
        first = store.check_rate_limit_bucket(bucket=bucket, limit=2, window_seconds=60, now=100)
        second = store.check_rate_limit_bucket(bucket=bucket, limit=2, window_seconds=60, now=101)
        denied = store.check_rate_limit_bucket(bucket=bucket, limit=2, window_seconds=60, now=102)
        self.assertTrue(first["allowed"])
        self.assertEqual(second["remaining"], 0)
        self.assertFalse(denied["allowed"])
        at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
        record = record_workspace_usage_to_path(state_path=PROJECT_ROOT / "outputs" / "quota.json", workspace_id="postgres_quota_contract", usage={"total_tokens": 10}, at=at, store=store)
        self.assertEqual(record["quota_store"]["type"], "postgres")
        self.assertEqual(store.workspace_current_usage(workspace_id="postgres_quota_contract", period_key="daily:2026-06-28", usage_keys=["requests", "total_tokens"])["total_tokens"], 10.0)


if __name__ == "__main__":
    unittest.main()
