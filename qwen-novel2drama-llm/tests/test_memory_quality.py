from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.memory_quality import compress_items, conflict_groups, duplicate_groups, merge_group, quality_report


class MemoryQualityTests(unittest.TestCase):
    def test_duplicate_merge_compress_and_conflict(self) -> None:
        items = [
            {"id": "m1", "scope": "project", "project_id": "p1", "content": "alpha is lead", "tags": ["a"], "importance": 0.5, "metadata": {"subject": "alpha", "label": "yes"}},
            {"id": "m2", "scope": "project", "project_id": "p1", "content": "alpha is lead", "tags": ["b"], "importance": 0.9, "metadata": {"subject": "alpha", "label": "yes"}},
            {"id": "m3", "scope": "project", "project_id": "p1", "content": "alpha is not lead", "tags": ["c"], "importance": 0.7, "metadata": {"subject": "alpha", "label": "no"}},
        ]
        self.assertEqual(len(duplicate_groups(items)), 1)
        self.assertEqual(len(conflict_groups(items)), 1)
        merged = merge_group(items[:2])
        self.assertEqual(merged["importance"], 0.9)
        self.assertEqual(merged["tags"], ["a", "b"])
        compressed = compress_items(items, max_items=2)
        self.assertEqual(compressed["used_count"], 2)
        report = quality_report(items)
        self.assertEqual(report["status"], "review")


if __name__ == "__main__":
    unittest.main()
