from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services"))

from services.memory_store import delete_memory, is_expired, read_memory, search_memory, write_memory


class MemoryStoreTests(unittest.TestCase):
    def test_write_and_read_memory(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            path = Path(tmpdir) / "memory.jsonl"
            item = write_memory(path, {"scope": "project", "project_id": "p1", "content": "角色林晚是女主", "tags": ["character"]})
            self.assertTrue(item["id"].startswith("mem_"))
            items = read_memory(path)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["project_id"], "p1")

    def test_search_respects_scope(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            path = Path(tmpdir) / "memory.jsonl"
            write_memory(path, {"scope": "project", "project_id": "p1", "content": "短剧角色设定", "tags": ["drama"]})
            write_memory(path, {"scope": "project", "project_id": "p2", "content": "短剧角色设定", "tags": ["drama"]})
            results = search_memory(path, {"scope": "project", "project_id": "p1", "query": "短剧"})
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["project_id"], "p1")

    def test_search_respects_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            path = Path(tmpdir) / "memory.jsonl"
            write_memory(path, {"scope": "user", "owner_id": "u1", "content": "公开偏好", "sensitivity": "public"})
            write_memory(path, {"scope": "user", "owner_id": "u1", "content": "秘密信息", "sensitivity": "secret"})
            results = search_memory(path, {"scope": "user", "owner_id": "u1", "max_sensitivity": "internal"})
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["sensitivity"], "public")

    def test_ttl_expiration(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            path = Path(tmpdir) / "memory.jsonl"
            item = write_memory(path, {"scope": "session", "session_id": "s1", "content": "临时记忆", "ttl_seconds": 0})
            self.assertTrue(is_expired(item))
            results = search_memory(path, {"scope": "session", "session_id": "s1"})
            self.assertEqual(results, [])

    def test_delete_memory_soft_deletes(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            path = Path(tmpdir) / "memory.jsonl"
            item = write_memory(path, {"scope": "task", "task_id": "t1", "content": "任务记忆"})
            deleted = delete_memory(path, item["id"])
            self.assertIsNotNone(deleted)
            self.assertEqual(read_memory(path), [])
            self.assertEqual(len(read_memory(path, include_deleted=True)), 1)


if __name__ == "__main__":
    unittest.main()
