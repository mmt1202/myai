from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_code_symbols import build_symbol_index, collect_symbols  # noqa: E402
from search_code_symbols import search_symbols  # noqa: E402


class CodeSymbolTests(unittest.TestCase):
    def test_collect_symbols_finds_class_function_and_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "demo.py"
            source.write_text("import os\n\nclass Demo:\n    def run(self):\n        return os.getcwd()\n", encoding="utf-8")
            result = collect_symbols(source, root)
            names = {item["name"] for item in result["symbols"]}
            self.assertIn("Demo", names)
            self.assertIn("run", names)
            self.assertEqual(result["imports"][0]["name"], "os")

    def test_build_symbol_index_handles_project(self) -> None:
        index = build_symbol_index(PROJECT_ROOT)
        self.assertGreater(index["file_count"], 0)
        paths = {item["path"] for item in index["files"]}
        self.assertIn("scripts/build_code_symbols.py", paths)

    def test_search_symbols_finds_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index_path = root / "symbols.json"
            index_path.write_text(
                json.dumps({"files": [{"path": "a.py", "symbols": [{"name": "build_index", "type": "function", "line": 1}]}]}),
                encoding="utf-8",
            )
            results = search_symbols(index_path, "build")
            self.assertEqual(results[0]["name"], "build_index")


if __name__ == "__main__":
    unittest.main()
