from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services"))

from services.rule_engine import evaluate_rules, load_rules


class RuleEngineTests(unittest.TestCase):
    def load_default_rules(self) -> dict:
        return load_rules(PROJECT_ROOT / "configs" / "rules" / "default_rules.yaml")

    def test_local_only_blocks_external_provider(self) -> None:
        result = evaluate_rules(
            self.load_default_rules(),
            {"request": {"privacy": {"local_only": True}}, "candidate": {"provider": "openai_compatible"}},
        )
        self.assertEqual(result["decision"], "deny")
        self.assertTrue(any(rule["id"] == "local_only_blocks_external_provider" for rule in result["matched_rules"]))

    def test_budget_limit_denies_high_cost(self) -> None:
        result = evaluate_rules(
            self.load_default_rules(),
            {"request": {"budget": {"max_estimated_cost": 0.01}}, "candidate": {"estimated_cost": {"estimated": 0.02}}},
        )
        self.assertEqual(result["decision"], "deny")

    def test_secret_external_provider_requires_review(self) -> None:
        result = evaluate_rules(
            self.load_default_rules(),
            {"request": {"max_sensitivity": "secret"}, "candidate": {"provider": "external"}},
        )
        self.assertEqual(result["decision"], "review")

    def test_tool_write_requires_review(self) -> None:
        result = evaluate_rules(
            self.load_default_rules(),
            {"tool": {"write_files": True, "requires_confirmation": True}},
        )
        self.assertEqual(result["decision"], "review")

    def test_memory_secret_requires_owner_scope(self) -> None:
        result = evaluate_rules(
            self.load_default_rules(),
            {"memory": {"sensitivity": "secret"}, "request": {}},
        )
        self.assertEqual(result["decision"], "deny")

    def test_default_allow_when_no_rule_matches(self) -> None:
        result = evaluate_rules(self.load_default_rules(), {"request": {}, "candidate": {"provider": "local"}})
        self.assertEqual(result["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
