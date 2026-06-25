from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FoundationCapabilityMatrixTests(unittest.TestCase):
    def test_matrix_has_universal_positioning(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "foundation_capability_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(data["foundation_positioning"], "local universal AI foundation")
        self.assertIn("capabilities", data)

    def test_matrix_has_implemented_and_planned_capabilities(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "foundation_capability_matrix.json").read_text(encoding="utf-8"))
        statuses = {item["status"] for item in data["capabilities"]}
        self.assertIn("implemented", statuses)
        self.assertIn("planned", statuses)

    def test_short_drama_is_product_not_base_boundary(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "foundation_capability_matrix.json").read_text(encoding="utf-8"))
        drama = [item for item in data["capabilities"] if item["id"] == "drama_factory"]
        self.assertEqual(drama[0]["stage"], "Product")


if __name__ == "__main__":
    unittest.main()
