from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from create_unified_diff import apply_change, create_diff, replace_exact, safe_project_path  # noqa: E402


class UnifiedDiffTests(unittest.TestCase):
    def test_replace_exact_requires_expected_count(self) -> None:
        new_text, count = replace_exact("hello world", "world", "ai", 1)
        self.assertEqual(new_text, "hello ai")
        self.assertEqual(count, 1)
        with self.assertRaises(ValueError):
            replace_exact("x x", "x", "y", 1)

    def test_apply_append_change(self) -> None:
        new_text, operation = apply_change("hello", {"append": "world"})
        self.assertEqual(new_text, "hello\nworld")
        self.assertEqual(operation["operation"], "append")

    def test_safe_project_path_blocks_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            with self.assertRaises(ValueError):
                safe_project_path(root, "../outside.txt")

    def test_create_diff_does_not_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_text("old\n", encoding="utf-8")
            result = create_diff(root, {"task": "demo", "changes": [{"path": "a.txt", "find": "old", "replace": "new", "count": 1}]})
            self.assertIn("-old", result["diff"])
            self.assertIn("+new", result["diff"])
            self.assertEqual(source.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
