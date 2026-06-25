from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from model_version_registry import ModelVersionError, resolve_model_paths  # noqa: E402


class ModelVersionResolverTests(unittest.TestCase):
    def test_resolve_active_version_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "versions.json"
            path.write_text(
                json.dumps(
                    {
                        "active_version": "v1",
                        "versions": [
                            {
                                "version": "v1",
                                "base_model": "Qwen/base",
                                "adapter_path": "saves/v1",
                                "merged_model_path": "models/v1",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            model_path, adapter_path, item = resolve_model_paths(path)
            self.assertEqual(model_path, "models/v1")
            self.assertEqual(adapter_path, "saves/v1")
            self.assertEqual(item["version"], "v1")

    def test_missing_active_version_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "versions.json"
            path.write_text(json.dumps({"active_version": None, "versions": []}), encoding="utf-8")
            with self.assertRaises(ModelVersionError):
                resolve_model_paths(path)


if __name__ == "__main__":
    unittest.main()
