from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.sqlite_memory_store import SQLiteMemoryStore


class SQLiteMemoryStoreTests(unittest.TestCase):
    def test_write_search_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteMemoryStore(Path(tmpdir) / "memory.sqlite")
            item = store.write({"scope": "project", "project_id": "p1", "content": "林晚是短剧女主", "tags": ["drama"], "importance": 0.9})
            self.assertTrue(item["id"].startswith("mem_"))
            self.assertEqual(store.metadata()["type"], "sqlite")
            results = store.search({"scope": "project", "project_id": "p1", "query": "林晚", "tags": ["drama"]})
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["content"], "林晚是短剧女主")
            deleted = store.delete(item["id"])
            self.assertIsNotNone(deleted)
            self.assertEqual(store.search({"scope": "project", "project_id": "p1", "query": "林晚"}), [])
            self.assertEqual(len(store.read(include_deleted=True)), 1)

    def test_ttl_and_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteMemoryStore(Path(tmpdir) / "memory.sqlite")
            store.write({"scope": "user", "owner_id": "u1", "content": "公开偏好", "sensitivity": "public"})
            store.write({"scope": "user", "owner_id": "u1", "content": "秘密偏好", "sensitivity": "secret"})
            store.write({"scope": "user", "owner_id": "u1", "content": "过期偏好", "ttl_seconds": 0})
            results = store.search({"scope": "user", "owner_id": "u1", "max_sensitivity": "internal"})
            contents = {item["content"] for item in results}
            self.assertIn("公开偏好", contents)
            self.assertNotIn("秘密偏好", contents)
            self.assertNotIn("过期偏好", contents)


if __name__ == "__main__":
    unittest.main()
