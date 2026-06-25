from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from runtime_registry import UnsupportedRuntimeError, ensure_text_generation_runtime, load_runtime_registry  # noqa: E402


class RuntimeRegistryTests(unittest.TestCase):
    def test_default_runtime(self) -> None:
        registry = load_runtime_registry(PROJECT_ROOT / "configs" / "model_registry.json")
        runtime = registry.resolve()
        self.assertEqual(runtime.name, "qwen-text-p0")
        self.assertEqual(runtime.capability, "text_generation")
        ensure_text_generation_runtime(runtime)

    def test_planned_runtime(self) -> None:
        registry = load_runtime_registry(PROJECT_ROOT / "configs" / "model_registry.json")
        runtime = registry.resolve("qwen-vl-p2")
        self.assertEqual(runtime.status, "planned")
        with self.assertRaises(UnsupportedRuntimeError):
            ensure_text_generation_runtime(runtime)

    def test_filter_by_status(self) -> None:
        registry = load_runtime_registry(PROJECT_ROOT / "configs" / "model_registry.json")
        implemented = registry.list_runtimes(status="implemented")
        planned = registry.list_runtimes(status="planned")
        self.assertEqual([item.name for item in implemented], ["qwen-text-p0"])
        self.assertTrue(any(item.name == "qwen-agent-p3" for item in planned))


if __name__ == "__main__":
    unittest.main()
