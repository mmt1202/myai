from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.model_tool_loop_usage import aggregate_model_tool_loop_usage, apply_aggregation_to_provider_response, provider_response_model_id


class ModelToolLoopUsageAggregationTests(unittest.TestCase):
    def registry(self) -> dict:
        return {
            "default_currency": "USD",
            "instances": [
                {
                    "id": "m1",
                    "provider": "test_provider",
                    "cost": {"input_per_1m": 1.0, "output_per_1m": 2.0},
                }
            ],
        }

    def test_provider_response_model_id_handles_dict_and_string(self) -> None:
        self.assertEqual(provider_response_model_id({"model": {"model_id": "m1"}}), "m1")
        self.assertEqual(provider_response_model_id({"model": "m2"}), "m2")
        self.assertEqual(provider_response_model_id({}, "fallback"), "fallback")

    def test_aggregate_model_tool_loop_usage_sums_initial_and_rounds(self) -> None:
        initial = {
            "status": "ok",
            "model": {"model_id": "m1", "provider": "test_provider"},
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "cost": {"currency": "USD", "actual": 0.00002, "estimated": 0.00002},
        }
        summary = {
            "status": "ok",
            "rounds": [
                {
                    "round": 1,
                    "provider_response": {
                        "status": "ok",
                        "model": {"model_id": "m1", "provider": "test_provider"},
                        "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
                    },
                }
            ],
        }
        report = aggregate_model_tool_loop_usage(initial_provider_response=initial, model_tool_loop_summary=summary, instances_registry=self.registry(), selected_model_id="m1")
        self.assertEqual(report["provider_call_count"], 2)
        self.assertEqual(report["usage"]["input_tokens"], 30)
        self.assertEqual(report["usage"]["output_tokens"], 15)
        self.assertEqual(report["usage"]["total_tokens"], 45)
        self.assertEqual(report["by_model"]["m1"]["call_count"], 2)
        self.assertEqual(report["by_provider"]["test_provider"]["usage"]["total_tokens"], 45)
        self.assertGreater(report["cost"]["actual"], 0)

    def test_missing_usage_generates_warning(self) -> None:
        report = aggregate_model_tool_loop_usage(
            initial_provider_response={"status": "ok", "model": {"model_id": "m1"}, "usage": {}},
            model_tool_loop_summary={"status": "ok", "rounds": []},
            instances_registry=self.registry(),
            selected_model_id="m1",
        )
        self.assertIn("some_provider_calls_missing_usage", report["warnings"])
        self.assertEqual(report["missing_usage_sources"], ["initial_provider_response"])

    def test_apply_aggregation_to_provider_response(self) -> None:
        response = {"status": "ok", "usage": {"total_tokens": 1}}
        aggregation = {"provider_call_count": 2, "usage": {"total_tokens": 10}, "cost": {"actual": 0.1}, "warnings": []}
        updated = apply_aggregation_to_provider_response(response, aggregation)
        self.assertEqual(updated["usage"]["total_tokens"], 10)
        self.assertEqual(updated["cost"]["actual"], 0.1)
        self.assertEqual(updated["model_tool_loop_usage_aggregation"]["provider_call_count"], 2)


if __name__ == "__main__":
    unittest.main()
