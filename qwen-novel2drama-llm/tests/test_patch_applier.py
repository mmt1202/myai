from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_patch_spec import CONFIRM_TOKEN, apply_patch_spec  # noqa: E402


class PatchApplierTests(unittest.TestCase):
    def test_dry_run_does_not_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_text("old\n", encoding="utf-8")
            report = apply_patch_spec(root, {"task": "demo", "changes": [{"path": "a.txt", "find": "old", "replace": "new", "count": 1}]}, dry_run=True)
            self.assertEqual(report["changed_file_count"], 1)
            self.assertEqual(source.read_text(encoding="utf-8"), "old\n")

    def test_write_requires_confirm_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("old\n", encoding="utf-8")
            with self.assertRaises(PermissionError):
                apply_patch_spec(root, {"changes": [{"path": "a.txt", "find": "old", "replace": "new", "count": 1}]}, dry_run=False, confirm=None)

    def test_confirmed_apply_modifies_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "a.txt"
            source.write_text("old\n", encoding="utf-8")
            report = apply_patch_spec(root, {"changes": [{"path": "a.txt", "find": "old", "replace": "new", "count": 1}]}, dry_run=False, confirm=CONFIRM_TOKEN)
            self.assertEqual(report["changed_file_count"], 1)
            self.assertEqual(source.read_text(encoding="utf-8"), "new\n")

    def test_blocks_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(ValueError):
                apply_patch_spec(root, {"changes": [{"path": "../outside.txt", "append": "bad"}]}, dry_run=True)


if __name__ == "__main__":
    unittest.main()
