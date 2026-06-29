from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from billing.exporter import export_workspace_costs
from billing.reconciliation import reconcile_usage, summarize_provider_records
from billing.usage_records import load_usage_records


class BillingUsageRecordsTests(unittest.TestCase):
    def test_load_summarize_reconcile_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "usage.json"
            path.write_text(json.dumps({"items": [
                {"provider": "demo", "record_id": "r1", "workspace_id": "w1", "date": "2026-06-29", "model": "m1", "input_tokens": 10, "output_tokens": 20, "cost": 0.3},
                {"provider": "demo", "record_id": "r2", "workspace_id": "w1", "date": "2026-06-29", "model": "m1", "input_tokens": 5, "output_tokens": 5, "cost": 0.1}
            ]}, ensure_ascii=False), encoding="utf-8")
            records = load_usage_records(path, provider="demo")
            self.assertEqual(len(records), 2)
            summary = summarize_provider_records(records)
            self.assertEqual(summary["workspaces"]["w1"]["cost"], 0.4)
            matched = reconcile_usage({"workspaces": {"w1": {"cost": 0.4}}}, records)
            self.assertEqual(matched["status"], "matched")
            mismatch = reconcile_usage({"workspaces": {"w1": {"cost": 0.1}}}, records)
            self.assertEqual(mismatch["status"], "mismatch")
            exported = export_workspace_costs(summary, Path(tmpdir) / "billing.csv")
            self.assertEqual(exported["row_count"], 1)


if __name__ == "__main__":
    unittest.main()
