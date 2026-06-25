from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from create_patch_plan import create_patch_plan, rank_files, rank_symbols, tokenize  # noqa: E402


class PatchPlanTests(unittest.TestCase):
    def test_tokenize_removes_common_words(self) -> None:
        self.assertIn("api_server", tokenize("add api_server endpoint"))
        self.assertNotIn("add", tokenize("add api_server endpoint"))

    def test_rank_files_matches_path_keywords(self) -> None:
        context_index = {"files": [{"path": "inference/api_server.py", "sha256": "x", "chunk_count": 1}]}
        ranked = rank_files(context_index, "update api_server health", limit=5)
        self.assertEqual(ranked[0]["path"], "inference/api_server.py")

    def test_rank_symbols_matches_symbol_keywords(self) -> None:
        symbol_index = {"files": [{"path": "inference/api_server.py", "symbols": [{"name": "health", "type": "function", "line": 10}]}]}
        ranked = rank_symbols(symbol_index, "update health endpoint", limit=5)
        self.assertEqual(ranked[0]["name"], "health")

    def test_create_patch_plan_contains_steps_and_tests(self) -> None:
        context_index = {"files": [{"path": "tests/test_api_server.py", "sha256": "x", "chunk_count": 1}]}
        symbol_index = {"files": []}
        plan = create_patch_plan("update api server tests", context_index, symbol_index)
        self.assertIn("target_files", plan)
        self.assertIn("steps", plan)
        self.assertIn("python -m unittest discover tests", plan["tests_to_run"])


if __name__ == "__main__":
    unittest.main()
