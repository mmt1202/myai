from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.workspace_quota import (
    check_workspace_quota,
    check_workspace_quota_from_paths,
    period_key,
    record_workspace_usage,
    record_workspace_usage_to_path,
    resolve_workspace_limits,
    usage_increment,
)


class WorkspaceQuotaTests(unittest.TestCase):
    def test_period_key(self) -> None:
        at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(period_key("daily", at), "daily:2026-06-28")
        self.assertEqual(period_key("monthly", at), "monthly:2026-06")

    def test_usage_increment_normalizes_usage_and_cost(self) -> None:
        increment = usage_increment({"prompt_tokens": 10, "completion_tokens": 5}, {"actual": 0.25})
        self.assertEqual(increment["requests"], 1.0)
        self.assertEqual(increment["input_tokens"], 10.0)
        self.assertEqual(increment["output_tokens"], 5.0)
        self.assertEqual(increment["total_tokens"], 15.0)
        self.assertEqual(increment["cost"], 0.25)

    def test_resolve_workspace_limits_merges_default_and_workspace(self) -> None:
        config = {
            "default": {"enabled": True, "daily": {"max_requests": 10, "max_cost": 5}},
            "workspaces": {"w1": {"daily": {"max_cost": 1}}},
        }
        limits = resolve_workspace_limits(config, "w1")
        self.assertEqual(limits["daily"]["max_requests"], 10)
        self.assertEqual(limits["daily"]["max_cost"], 1)

    def test_check_workspace_quota_allows_under_limit(self) -> None:
        config = {"default": {"enabled": True, "daily": {"max_requests": 2, "max_total_tokens": 100, "max_cost": 1.0}}}
        state = {"workspaces": {}, "events": []}
        report = check_workspace_quota(config=config, state=state, workspace_id="w1", usage={"total_tokens": 20}, cost={"actual": 0.1})
        self.assertTrue(report["allowed"])
        self.assertEqual(report["decision"], "allowed")

    def test_check_workspace_quota_denies_over_limit(self) -> None:
        config = {"default": {"enabled": True, "daily": {"max_requests": 1, "max_total_tokens": 25, "max_cost": 0.2}}}
        state = {"workspaces": {"w1": {"daily:2026-06-28": {"requests": 1, "total_tokens": 20, "cost": 0.1}}}, "events": []}
        at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
        report = check_workspace_quota(config=config, state=state, workspace_id="w1", usage={"total_tokens": 10}, cost={"actual": 0.15}, at=at)
        self.assertFalse(report["allowed"])
        metrics = {item["metric"] for item in report["violations"]}
        self.assertIn("requests", metrics)
        self.assertIn("total_tokens", metrics)
        self.assertIn("cost", metrics)

    def test_record_workspace_usage_updates_daily_and_monthly(self) -> None:
        state = {"workspaces": {}, "events": []}
        at = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
        result = record_workspace_usage(state=state, workspace_id="w1", usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, cost={"actual": 0.3}, at=at)
        self.assertEqual(result["updated_periods"]["daily:2026-06-28"]["requests"], 1.0)
        self.assertEqual(result["updated_periods"]["monthly:2026-06"]["total_tokens"], 15.0)
        self.assertEqual(len(state["events"]), 1)

    def test_path_helpers(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            config_path = Path(tmpdir) / "workspace_quotas.json"
            state_path = Path(tmpdir) / "workspace_quota_state.json"
            config_path.write_text('{"default":{"enabled":true,"daily":{"max_requests":5,"max_total_tokens":100}}}', encoding="utf-8")
            check = check_workspace_quota_from_paths(config_path=config_path, state_path=state_path, workspace_id="w1", usage={"total_tokens": 10})
            self.assertTrue(check["allowed"])
            record = record_workspace_usage_to_path(state_path=state_path, workspace_id="w1", usage={"total_tokens": 10}, metadata={"request_id": "r1"})
            self.assertEqual(record["workspace_id"], "w1")
            self.assertTrue(state_path.exists())


if __name__ == "__main__":
    unittest.main()
