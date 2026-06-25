from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from read_context_chunk import read_chunk  # noqa: E402
from search_context_index import search_index  # noqa: E402


class ContextSearchAndChunkTests(unittest.TestCase):
    def test_search_index_finds_line_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.py"
            source.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
            index = root / "index.json"
            index.write_text(json.dumps({"files": [{"path": "a.py", "sha256": "x", "chunk_count": 1}]}), encoding="utf-8")
            results = search_index(root, index, "hello")
            self.assertEqual(results[0]["path"], "a.py")
            self.assertEqual(results[0]["matches"][0]["line"], 1)

    def test_read_context_chunk_reads_expected_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_text("abcdefghij", encoding="utf-8")
            result = read_chunk(root, "a.txt", chunk_id=1, chunk_chars=4)
            self.assertEqual(result["text"], "efgh")
            self.assertEqual(result["start_char"], 4)


if __name__ == "__main__":
    unittest.main()
