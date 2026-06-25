from __future__ import annotations

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeRegistryTests(unittest.TestCase):
    def test_registry_has_default_runtime(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "model_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(data["default_runtime"], "qwen-text-p0")
        self.assertTrue(data["runtimes"])

    def test_registry_tracks_planned_and_implemented_items(self) -> None:
        data = json.loads((PROJECT_ROOT / "configs" / "model_registry.json").read_text(encoding="utf-8"))
        statuses = {item["status"] for item in data["runtimes"]}
        self.assertIn("implemented", statuses)
        self.assertIn("planned", statuses)


if __name__ == "__main__":
    unittest.main()
