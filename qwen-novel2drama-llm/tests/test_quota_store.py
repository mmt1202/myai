from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.quota_store import FileQuotaStore, SQLiteQuotaStore, build_quota_store, quota_store_from_env
from services.rate_limiter import RateLimitError, check_rate_limit
from services.workspace_quota import check_workspace_quota_from_paths, record_workspace_usage_to_path


class QuotaStoreTests(unittest.TestCase):
    def test_build_quota_store_selects_file_and_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_store = build_quota_store("file", rate_limit_state_path=root / "rate.json", workspace_quota_state_path=root / "quota.json")
            sqlite_store = build_quota_store("sqlite", rate_limit_state_path=root / "rate.json", workspace_quota_state_path=root / "quota.json", sqlite_path=root / "quota.sqlite")
            self.assertIsInstance(file_store, FileQuotaStore)
            self.assertIsInstance(sqlite_store, SQLiteQuotaStore)
            self.assertEqual(sqlite_store.metadata()["db_path"], str(root / "quota.sqlite"))

    def test_file_store_rate_limit_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = FileQuotaStore(rate_limit_state_path=root / "rate.json", workspace_quota_state_path=root / "quota.json")
            first = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=100)
            second = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=101)
            denied = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=102)
            self.assertTrue(first["allowed"])
            self.assertEqual(second["remaining"], 0)
            self.assertFalse(denied["allowed"])
            self.assertTrue((root / "rate.json").exists())

    def test_sqlite_store_rate_limit_bucket_is_atomic_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteQuotaStore(Path(tmpdir) / "quota.sqlite")
            first = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=100)
            second = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=101)
            denied = store.check_rate_limit_bucket(bucket="k|scope|w", limit=2, window_seconds=60, now=102)
            self.assertTrue(first["allowed"])
            self.assertEqual(second["remaining"], 0)
            self.assertFalse(denied["allowed"])
            self.assertEqual(store.metadata()["type"], "sqlite")

    def test_check_rate_limit_accepts_sqlite_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteQuotaStore(Path(tmpdir) / "quota.sqlite")
            config = {"default": {"enabled": True, "limit": 1, "window_seconds": 60}}
            result = check_rate_limit(Path(tmpdir) / "rate.json", config, key_id="k1", required_scope="model:invoke", workspace_id="w1", now=100, store=store)
            self.assertEqual(result["quota_store"]["type"], "sqlite")
            with self.assertRaises(RateLimitError) as ctx:
                check_rate_limit(Path(tmpdir) / "rate.json", config, key_id="k1", required_scope="model:invoke", workspace_id="w1", now=101, store=store)
            self.assertEqual(ctx.exception.quota_store["type"], "sqlite")

    def test_workspace_usage_records_to_sqlite_periods(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = SQLiteQuotaStore(root / "quota.sqlite")
            at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
            record = record_workspace_usage_to_path(state_path=root / "quota.json", workspace_id="w1", usage={"total_tokens": 10}, cost={"actual": 0.25}, at=at, metadata={"request_id": "r1"}, store=store)
            self.assertEqual(record["quota_store"]["type"], "sqlite")
            self.assertEqual(record["updated_periods"]["daily:2026-06-28"]["requests"], 1.0)
            self.assertEqual(store.workspace_current_usage(workspace_id="w1", period_key="monthly:2026-06", usage_keys=["requests", "total_tokens", "cost"])["total_tokens"], 10.0)

    def test_workspace_quota_check_uses_sqlite_current_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "quota_config.json"
            config_path.write_text('{"default":{"enabled":true,"daily":{"max_requests":1,"max_total_tokens":15}}}', encoding="utf-8")
            store = SQLiteQuotaStore(root / "quota.sqlite")
            at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
            record_workspace_usage_to_path(state_path=root / "quota.json", workspace_id="w1", usage={"total_tokens": 10}, at=at, store=store)
            report = check_workspace_quota_from_paths(config_path=config_path, state_path=root / "quota.json", workspace_id="w1", usage={"total_tokens": 10}, at=at, store=store)
            self.assertFalse(report["allowed"])
            self.assertEqual(report["quota_store"]["type"], "sqlite")
            metrics = {item["metric"] for item in report["violations"]}
            self.assertIn("requests", metrics)
            self.assertIn("total_tokens", metrics)

    def test_quota_store_from_env_uses_sqlite_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_backend = os.environ.get("FOUNDATION_QUOTA_BACKEND")
            old_db = os.environ.get("FOUNDATION_QUOTA_DB")
            os.environ["FOUNDATION_QUOTA_BACKEND"] = "sqlite"
            os.environ["FOUNDATION_QUOTA_DB"] = str(root / "quota.sqlite")
            try:
                store = quota_store_from_env(rate_limit_state_path=root / "rate.json", workspace_quota_state_path=root / "quota.json")
                self.assertEqual(store.metadata()["type"], "sqlite")
                self.assertEqual(store.metadata()["db_path"], str(root / "quota.sqlite"))
            finally:
                if old_backend is None:
                    os.environ.pop("FOUNDATION_QUOTA_BACKEND", None)
                else:
                    os.environ["FOUNDATION_QUOTA_BACKEND"] = old_backend
                if old_db is None:
                    os.environ.pop("FOUNDATION_QUOTA_DB", None)
                else:
                    os.environ["FOUNDATION_QUOTA_DB"] = old_db


if __name__ == "__main__":
    unittest.main()
