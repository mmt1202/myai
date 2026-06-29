from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class ModelVersionsTests(unittest.TestCase):
    def test_active_version_is_registered(self) -> None:
        registry = json.loads((PROJECT_ROOT / "configs" / "model_versions.json").read_text(encoding="utf-8"))
        active = registry.get("active_version")
        self.assertIsInstance(active, str)
        self.assertTrue(active)
        versions = {item.get("version"): item for item in registry.get("versions") or []}
        self.assertIn(active, versions)
        self.assertIn(versions[active].get("channel"), {"dev", "stable", "experimental"})
        self.assertIn("base_model", versions[active])
        self.assertIn("adapter", versions[active])


if __name__ == "__main__":
    unittest.main()
