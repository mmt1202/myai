from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from plan_training_run import build_manifest, read_simple_yaml  # noqa: E402


class TrainingRunPlannerTests(unittest.TestCase):
    def test_read_simple_yaml(self) -> None:
        config = read_simple_yaml(PROJECT_ROOT / "configs" / "qwen2_5_1_5b_lora.yaml")
        self.assertEqual(config["stage"], "sft")
        self.assertEqual(config["finetuning_type"], "lora")
        self.assertEqual(config["dataset"], "novel2drama")

    def test_build_manifest(self) -> None:
        manifest = build_manifest(PROJECT_ROOT, PROJECT_ROOT / "configs" / "qwen2_5_1_5b_lora.yaml", "unit-test-run")
        self.assertEqual(manifest["run_name"], "unit-test-run")
        self.assertEqual(manifest["dataset"], "novel2drama")
        self.assertGreater(manifest["train_rows"], 0)
        self.assertIn("train_linux_macos", manifest["commands"])


if __name__ == "__main__":
    unittest.main()
