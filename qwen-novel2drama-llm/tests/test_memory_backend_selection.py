from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.memory_store import FileMemoryStore, build_memory_store, memory_store_from_env
from services.sqlite_memory_store import SQLiteMemoryStore
from services.vector_memory_store import VectorMemoryStore


class MemoryBackendSelectionTests(unittest.TestCase):
    def test_build_memory_store_selects_backends(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertIsInstance(build_memory_store("file", jsonl_path=root / "memory.jsonl"), FileMemoryStore)
            self.assertIsInstance(build_memory_store("sqlite", sqlite_path=root / "memory.sqlite"), SQLiteMemoryStore)
            self.assertIsInstance(build_memory_store("vector", jsonl_path=root / "vector.jsonl"), VectorMemoryStore)

    def test_memory_store_from_env(self) -> None:
        old_backend = os.environ.get("FOUNDATION_MEMORY_BACKEND")
        old_db = os.environ.get("FOUNDATION_MEMORY_DB")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MEMORY_BACKEND"] = "sqlite"
                os.environ["FOUNDATION_MEMORY_DB"] = str(Path(tmpdir) / "memory.sqlite")
                store = memory_store_from_env(project_root=Path(tmpdir))
                self.assertEqual(store.metadata()["type"], "sqlite")
            finally:
                if old_backend is None:
                    os.environ.pop("FOUNDATION_MEMORY_BACKEND", None)
                else:
                    os.environ["FOUNDATION_MEMORY_BACKEND"] = old_backend
                if old_db is None:
                    os.environ.pop("FOUNDATION_MEMORY_DB", None)
                else:
                    os.environ["FOUNDATION_MEMORY_DB"] = old_db

    def test_unknown_backend_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_memory_store("unknown")


if __name__ == "__main__":
    unittest.main()
