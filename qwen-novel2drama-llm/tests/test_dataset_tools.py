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
from collect_web_text import html_to_text, load_sources  # noqa: E402
from analyze_dataset import analyze  # noqa: E402
from dedupe_dataset import dedupe  # noqa: E402
from sample_dataset import sample_lines  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT / "eval"))
from compare_results import compare  # noqa: E402


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

    def test_html_to_text_removes_script_content(self) -> None:
        html = "<html><body><h1>标题</h1><script>bad()</script><p>正文内容足够清晰。</p></body></html>"
        text = html_to_text(html)
        self.assertIn("标题", text)
        self.assertIn("正文内容", text)
        self.assertNotIn("bad()", text)

    def test_load_sources_requires_training_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sources.jsonl"
            path.write_text(json.dumps({"url": "https://example.com", "license": "unknown"}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_sources(path)

    def test_analyze_reports_duplicate_inputs(self) -> None:
        records = [
            {"instruction": "任务A", "input": "相同", "output": "这是一个足够长的输出。"},
            {"instruction": "任务B", "input": "相同", "output": "这是另一个足够长的输出。"},
        ]
        report = analyze(records, top_k=5)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["duplicate_input_count"], 1)

    def test_dedupe_dataset_by_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            output_path = Path(tmpdir) / "output.jsonl"
            rows = [
                {"instruction": "A", "input": "重复", "output": "1"},
                {"instruction": "B", "input": "重复", "output": "2"},
            ]
            input_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            total, kept = dedupe(input_path, output_path, mode="input")
            self.assertEqual((total, kept), (2, 1))

    def test_sample_dataset_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            output_a = Path(tmpdir) / "a.jsonl"
            output_b = Path(tmpdir) / "b.jsonl"
            input_path.write_text("\n".join(["{\"i\": 1}", "{\"i\": 2}", "{\"i\": 3}"]) + "\n", encoding="utf-8")
            self.assertEqual(sample_lines(input_path, output_a, size=2, seed=7), 2)
            self.assertEqual(sample_lines(input_path, output_b, size=2, seed=7), 2)
            self.assertEqual(output_a.read_text(encoding="utf-8"), output_b.read_text(encoding="utf-8"))

    def test_compare_results_aligns_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "base.jsonl"
            candidate_path = Path(tmpdir) / "candidate.jsonl"
            output_path = Path(tmpdir) / "compare.csv"
            base_path.write_text(json.dumps({"prompt": "p", "response": "base"}, ensure_ascii=False) + "\n", encoding="utf-8")
            candidate_path.write_text(json.dumps({"prompt": "p", "response": "candidate"}, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(compare(base_path, candidate_path, output_path), 1)
            csv_text = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("base_response", csv_text)
            self.assertIn("candidate", csv_text)

    def test_project_checker_current_project(self) -> None:
        self.assertEqual(collect_errors(PROJECT_ROOT), [])


if __name__ == "__main__":
    unittest.main()
