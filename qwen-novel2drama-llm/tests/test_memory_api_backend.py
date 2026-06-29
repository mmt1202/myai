from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

import inference.api_server as api_server


class MemoryApiBackendTests(unittest.TestCase):
    def test_api_uses_sqlite_memory_backend(self) -> None:
        old_backend = os.environ.get("FOUNDATION_MEMORY_BACKEND")
        old_db = os.environ.get("FOUNDATION_MEMORY_DB")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MEMORY_BACKEND"] = "sqlite"
                os.environ["FOUNDATION_MEMORY_DB"] = str(Path(tmpdir) / "memory.sqlite")
                write = api_server.memory_write_api({"item": {"scope": "project", "project_id": "p1", "content": "SQLite memory backend works"}})
                self.assertEqual(write["status"], "ok")
                self.assertEqual(write["output"]["memory_store"]["type"], "sqlite")
                search = api_server.memory_search_api({"scope": "project", "project_id": "p1", "query": "SQLite"})
                self.assertEqual(search["status"], "ok")
                self.assertEqual(search["output"]["memory_store"]["type"], "sqlite")
                self.assertEqual(len(search["output"]["items"]), 1)
            finally:
                if old_backend is None:
                    os.environ.pop("FOUNDATION_MEMORY_BACKEND", None)
                else:
                    os.environ["FOUNDATION_MEMORY_BACKEND"] = old_backend
                if old_db is None:
                    os.environ.pop("FOUNDATION_MEMORY_DB", None)
                else:
                    os.environ["FOUNDATION_MEMORY_DB"] = old_db


if __name__ == "__main__":
    unittest.main()
