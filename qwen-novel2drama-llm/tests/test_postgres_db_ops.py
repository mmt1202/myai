from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.postgres_db_ops import db_ops_health, forward_migration_plan, rollback_plan


class PostgresDbOpsTests(unittest.TestCase):
    def test_forward_migration_plan_wraps_migration_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "demo.sql"
            path.write_text("CREATE TABLE demo(id TEXT);\n", encoding="utf-8")
            plan = forward_migration_plan(path)
            self.assertEqual(plan["operation"], "forward_migration")
            self.assertEqual(plan["status"], "ready_for_apply")
            self.assertEqual(plan["migration"]["statement_count"], 1)
            self.assertTrue(plan["requires_backup"])

    def test_rollback_plan_is_manual_and_backup_required(self) -> None:
        plan = rollback_plan(migration_id="demo", reason="bad deploy")
        self.assertEqual(plan["status"], "manual_review_required")
        self.assertFalse(plan["reversible"])
        self.assertTrue(plan["requires_backup"])
        self.assertIn("demo", plan["migration_id"])

    def test_db_ops_health_reports_missing_backup(self) -> None:
        report = db_ops_health(migration_history_enabled=True, backup_configured=False)
        self.assertEqual(report["status"], "degraded")
        self.assertIn("verified_backup", report["missing"])


if __name__ == "__main__":
    unittest.main()
