from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.usage_reconciliation import normalize_usage, reconcile_provider_usage, reconciled_cost, reconciled_usage, usage_delta


class UsageReconciliationTests(unittest.TestCase):
    def test_normalize_usage_supports_provider_aliases(self) -> None:
        usage = normalize_usage({"prompt_tokens": 10, "completion_tokens": 5})
        self.assertEqual(usage["input_tokens"], 10)
        self.assertEqual(usage["output_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 15)

    def test_usage_delta(self) -> None:
        delta = usage_delta({"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30})
        self.assertEqual(delta["total_tokens"]["delta"], 15)
        self.assertEqual(delta["total_tokens"]["ratio"], 2.0)

    def test_reconcile_provider_usage_with_actual_provider_usage(self) -> None:
        instances = {
            "default_currency": "USD",
            "instances": [
                {
                    "id": "m1",
                    "provider": "test_provider",
                    "cost": {"input_per_1m": 1.0, "output_per_1m": 2.0},
                }
            ],
        }
        route_decision = {
            "request_id": "r1",
            "trace_id": "t1",
            "selected_model_id": "m1",
            "estimated_usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            "selected": {"provider": "test_provider", "estimated_cost": {"currency": "USD", "estimated": 0.00003}},
        }
        provider_response = {
            "request_id": "r1",
            "trace_id": "t1",
            "model": {"model_id": "m1", "provider": "test_provider"},
            "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        }
        report = reconcile_provider_usage(request_id="r1", trace_id="t1", route_decision=route_decision, provider_response=provider_response, instances_registry=instances)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["usage_source"], "provider_response")
        self.assertEqual(report["usage"]["delta"]["total_tokens"]["delta"], 5)
        self.assertEqual(report["cost"]["actual"], 0.00003)
        self.assertEqual(reconciled_usage(report)["total_tokens"], 25)
        self.assertEqual(reconciled_cost(report)["actual"], 0.00003)

    def test_reconcile_provider_usage_falls_back_to_estimate_when_provider_usage_missing(self) -> None:
        instances = {"default_currency": "USD", "instances": [{"id": "m1", "provider": "test_provider", "cost": {"input_per_1m": 1.0, "output_per_1m": 1.0}}]}
        route_decision = {
            "selected_model_id": "m1",
            "estimated_usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            "selected": {"provider": "test_provider", "estimated_cost": {"currency": "USD", "estimated": 0.00002}},
        }
        provider_response = {"model": {"model_id": "m1", "provider": "test_provider"}, "usage": {}}
        report = reconcile_provider_usage(request_id="r1", trace_id="t1", route_decision=route_decision, provider_response=provider_response, instances_registry=instances)
        self.assertEqual(report["status"], "fallback")
        self.assertEqual(report["usage_source"], "estimated_fallback")
        self.assertIn("provider_actual_usage_missing_or_zero", report["warnings"])
        self.assertEqual(report["usage"]["actual"]["total_tokens"], 20)


if __name__ == "__main__":
    unittest.main()
