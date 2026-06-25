from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_context_index import build_index, count_chunks, load_profile, select_files  # noqa: E402


class ContextIndexTests(unittest.TestCase):
    def test_count_chunks(self) -> None:
        self.assertEqual(count_chunks("", 4), 0)
        self.assertEqual(count_chunks("abcd", 4), 1)
        self.assertEqual(count_chunks("abcde", 4), 2)

    def test_select_files_respects_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "docs").mkdir()
            (root / "models").mkdir()
            (root / "docs" / "a.md").write_text("hello", encoding="utf-8")
            (root / "models" / "bad.md").write_text("ignore", encoding="utf-8")
            profile_path = root / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "profile": "test",
                        "include_globs": ["docs/*.md", "models/*.md"],
                        "exclude_dirs": ["models"],
                        "exclude_suffixes": [],
                        "max_file_bytes": 1000,
                        "chunk_chars": 4,
                    }
                ),
                encoding="utf-8",
            )
            profile = load_profile(profile_path)
            files = [path.relative_to(root).as_posix() for path in select_files(root, profile)]
            self.assertEqual(files, ["docs/a.md"])

    def test_build_index_for_current_project(self) -> None:
        index = build_index(PROJECT_ROOT, PROJECT_ROOT / "configs" / "context_profile.json")
        self.assertGreater(index["file_count"], 0)
        paths = {item["path"] for item in index["files"]}
        self.assertIn("README.md", paths)


if __name__ == "__main__":
    unittest.main()
