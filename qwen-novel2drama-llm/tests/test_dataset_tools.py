"""数据工具和项目检查脚本的轻量单元测试。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_project import collect_errors  # noqa: E402
from prepare_data import chunk_text  # noqa: E402
from split_dataset import read_lines, write_lines  # noqa: E402
from validate_dataset import validate_file  # noqa: E402


class DatasetToolTests(unittest.TestCase):
    """覆盖 JSONL 校验、拆分读写、小说切块和项目检查。"""

    def test_validate_dataset_accepts_valid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "train.jsonl"
            record = {"instruction": "任务", "input": "输入", "output": "输出"}
            path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(validate_file(path), 0)

    def test_validate_dataset_rejects_empty_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.jsonl"
            record = {"instruction": "任务", "input": "输入", "output": ""}
            path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertNotEqual(validate_file(path), 0)

    def test_split_helpers_round_trip_non_empty_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.jsonl"
            write_lines(path, ["{\"a\": 1}", "{\"b\": 2}"])
            self.assertEqual(read_lines(path), ["{\"a\": 1}", "{\"b\": 2}"])

    def test_chunk_text_respects_chunk_size(self) -> None:
        chunks = chunk_text("第一段。\n\n第二段很长很长。", chunk_size=6)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 6 for chunk in chunks))

    def test_project_checker_current_project(self) -> None:
        self.assertEqual(collect_errors(PROJECT_ROOT), [])


if __name__ == "__main__":
    unittest.main()
