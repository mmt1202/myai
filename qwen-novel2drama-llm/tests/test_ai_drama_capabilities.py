from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AIDramaCapabilityMatrixTests(unittest.TestCase):
    def test_ai_drama_is_primary_product_line(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "ai_drama_capability_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(data["product_line"], "ai_drama_comic_factory")
        self.assertEqual(data["priority"], "primary_product_after_foundation")

    def test_local_and_external_model_strategy_exist(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "ai_drama_capability_matrix.json").read_text(encoding="utf-8"))
        self.assertIn("story reasoning", data["model_strategy"]["local_foundation_model"])
        self.assertIn("text-to-video generation", data["model_strategy"]["external_models"])

    def test_critical_story_capabilities_exist(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "ai_drama_capability_matrix.json").read_text(encoding="utf-8"))
        ids = {item["id"] for item in data["capabilities"] if item["importance"] == "critical"}
        self.assertIn("story_understanding", ids)
        self.assertIn("episode_planning", ids)
        self.assertIn("multi_model_routing", ids)


if __name__ == "__main__":
    unittest.main()
