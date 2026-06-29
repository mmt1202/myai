from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.provider_catalog import catalog_summary, provider_instance_template, provider_spec
from providers.resilience import CircuitBreakerState, ProviderHealth, circuit_allows_request, fallback_plan, is_retryable_error, next_retry_delay_seconds, record_circuit_failure, record_circuit_success


class ProviderCatalogResilienceTests(unittest.TestCase):
    def test_catalog_has_required_providers(self) -> None:
        summary = catalog_summary()
        for name in ["deepseek", "qwen_dashscope", "anthropic", "gemini"]:
            self.assertIn(name, summary["providers"])
            self.assertEqual(provider_spec(name).runtime, "http_chat_completions")

    def test_provider_instance_template_contains_runtime_env_contract(self) -> None:
        item = provider_instance_template("deepseek", model_id="external.deepseek.chat")
        self.assertEqual(item["id"], "external.deepseek.chat")
        self.assertEqual(item["provider"], "deepseek")
        self.assertIn("api_key_env", item["runtime_config"])
        self.assertIn("text.chat", item["capabilities"])

    def test_retry_and_circuit_breaker(self) -> None:
        self.assertTrue(is_retryable_error({"code": "timeout"}))
        self.assertEqual(next_retry_delay_seconds(3, base_delay=1), 4)
        state = CircuitBreakerState(model_id="m1", failure_threshold=2)
        state = record_circuit_failure(state, now=100)
        self.assertTrue(circuit_allows_request(state, now=101))
        state = record_circuit_failure(state, now=101)
        self.assertFalse(circuit_allows_request(state, now=120))
        self.assertTrue(circuit_allows_request(state, now=200))
        self.assertEqual(record_circuit_success(state).status, "closed")

    def test_fallback_plan_ranks_by_health(self) -> None:
        candidates = [
            {"id": "a", "status": "configured", "capabilities": ["text.chat"]},
            {"id": "b", "status": "configured", "capabilities": ["text.chat"]},
        ]
        health = {"a": ProviderHealth(model_id="a", provider="p", success_count=1, failure_count=4), "b": ProviderHealth(model_id="b", provider="p", success_count=10, failure_count=0)}
        plan = fallback_plan(candidates, primary_model_id="a", health=health, required_capabilities=["text.chat"])
        self.assertEqual(plan["primary_model_id"], "a")
        self.assertEqual(plan["candidate_count"], 2)
        ranked = fallback_plan(candidates, health=health, required_capabilities=["text.chat"])
        self.assertEqual(ranked["candidates"][0]["id"], "b")


if __name__ == "__main__":
    unittest.main()
