from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from inference.model_router import route_model


class ConfigurableModelRouterTests(unittest.TestCase):
    def load_registry(self) -> dict:
        return json.loads((PROJECT_ROOT / "configs" / "model_instance_registry.json").read_text(encoding="utf-8"))

    def load_policy(self) -> dict:
        return json.loads((PROJECT_ROOT / "configs" / "model_routing_policy.json").read_text(encoding="utf-8"))

    def test_global_primary_selects_openai_candidate_without_hardcoding_in_request(self) -> None:
        result = route_model({"input": [{"type": "text", "text": "hello"}], "required_capabilities": ["text.chat"]}, self.load_registry(), policy=self.load_policy())
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["selected_model_id"], "external.openai.primary")
        self.assertEqual(result["model_preferences"]["primary_model"], "external.openai.primary")
        self.assertIn("global_primary", result["policy_hits"])

    def test_request_override_can_select_deepseek(self) -> None:
        result = route_model({"model_id": "external.deepseek.chat", "input": [{"type": "text", "text": "hello"}], "required_capabilities": ["text.chat"]}, self.load_registry(), policy=self.load_policy())
        self.assertEqual(result["selected_model_id"], "external.deepseek.chat")
        self.assertIn("request_primary", result["policy_hits"])

    def test_privacy_local_only_forces_local(self) -> None:
        result = route_model({"model_id": "external.openai.primary", "privacy": {"local_only": True}, "input": [{"type": "text", "text": "private"}], "required_capabilities": ["text.chat"]}, self.load_registry(), policy=self.load_policy())
        self.assertEqual(result["selected_model_id"], "local.qwen2_5_1_5b_instruct")
        self.assertIn("privacy_guard_private_models", result["policy_hits"])

    def test_drama_task_uses_drama_policy_primary(self) -> None:
        result = route_model({"task_type": "drama", "input": [{"type": "text", "text": "novel"}], "required_capabilities": ["text.chat"]}, self.load_registry(), policy=self.load_policy())
        self.assertEqual(result["selected_model_id"], "external.anthropic.claude")
        self.assertEqual(result["task_type"], "drama")

    def test_context_guard_uses_long_context_candidate(self) -> None:
        long_text = "x " * 40000
        result = route_model({"input": [{"type": "text", "text": long_text}], "required_capabilities": ["text.chat"], "expected_output_tokens": 1000}, self.load_registry(), policy=self.load_policy())
        self.assertEqual(result["status"], "routed")
        self.assertNotEqual(result["selected_model_id"], "local.qwen2_5_1_5b_instruct")

    def test_cost_guard_can_reject_nonzero_cost_when_limit_zero(self) -> None:
        registry = self.load_registry()
        for item in registry["instances"]:
            if item["id"] == "external.openai.primary":
                item["cost"] = {"input_per_1m": 10.0, "output_per_1m": 10.0}
        result = route_model({"model_id": "external.openai.primary", "fallback_models": ["local.qwen2_5_1_5b_instruct"], "max_estimated_cost": 0, "input": [{"type": "text", "text": "hello"}], "required_capabilities": ["text.chat"]}, registry, policy=self.load_policy())
        self.assertEqual(result["selected_model_id"], "local.qwen2_5_1_5b_instruct")
        reasons = {item["reason"] for item in result["rejected_candidates"]}
        self.assertIn("cost_guard", reasons)


if __name__ == "__main__":
    unittest.main()
