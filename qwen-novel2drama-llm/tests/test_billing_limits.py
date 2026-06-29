from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.billing_limits import billing_limit_plan, billing_reconciliation_status, global_rate_limit_health


class BillingLimitsTests(unittest.TestCase):
    def test_postgres_billing_plan_is_persistence_ready(self) -> None:
        plan = billing_limit_plan(quota_backend="postgres")
        self.assertEqual(plan["status"], "persistence_ready")
        self.assertFalse(plan["global_strong_consistency"])
        self.assertFalse(plan["external_billing_reconciliation"])

    def test_file_backend_is_local_only(self) -> None:
        plan = billing_limit_plan(quota_backend="file")
        self.assertEqual(plan["status"], "local_only")
        self.assertIn("file/sqlite backends are local-node only", plan["notes"])

    def test_global_rate_limit_health_requires_external_limiter_for_multi_region(self) -> None:
        report = global_rate_limit_health(quota_backend="postgres", regions=2, external_limiter_configured=False)
        self.assertEqual(report["status"], "degraded")
        self.assertIn("external_distributed_limiter", report["missing"])

    def test_billing_reconciliation_status_is_planned_until_import_and_export_exist(self) -> None:
        report = billing_reconciliation_status()
        self.assertEqual(report["status"], "planned")
        self.assertIn("invoice_import", report["missing"])
        self.assertIn("billing_export", report["missing"])


if __name__ == "__main__":
    unittest.main()
