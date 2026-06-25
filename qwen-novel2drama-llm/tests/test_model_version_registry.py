from __future__ import annotations

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from register_model_version import upsert_version  # noqa: E402


class ModelVersionRegistryTests(unittest.TestCase):
    def test_upsert_version_activates_requested_version(self) -> None:
        registry = {"active_version": None, "versions": []}
        entry = {"version": "v1", "status": "registered"}
        updated = upsert_version(registry, entry, activate=True)
        self.assertEqual(updated["active_version"], "v1")
        self.assertEqual(len(updated["versions"]), 1)

    def test_upsert_version_replaces_existing_version(self) -> None:
        registry = {"active_version": "v1", "versions": [{"version": "v1", "notes": "old"}]}
        entry = {"version": "v1", "notes": "new"}
        updated = upsert_version(registry, entry, activate=False)
        self.assertEqual(len(updated["versions"]), 1)
        self.assertEqual(updated["versions"][0]["notes"], "new")


if __name__ == "__main__":
    unittest.main()
