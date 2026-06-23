"""分析 instruction/input/output JSONL 数据集质量。"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

FIELDS = ("instruction", "input", "output")


def load_records(path: Path) -> list[dict[str, str]]:
    """读取 JSONL，并只保留合法对象。"""
    records: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if not line.strip():
                continue
            item: Any = json.loads(line)
            if isinstance(item, dict):
                records.append({field: str(item.get(field, "")) for field in FIELDS})
    return records


def length_stats(values: list[int]) -> dict[str, float | int]:
    """计算长度统计，空列表返回 0。"""
    if not values:
        return {"min": 0, "max": 0, "avg": 0}
    return {"min": min(values), "max": max(values), "avg": round(mean(values), 2)}


def analyze(records: list[dict[str, str]], top_k: int) -> dict[str, Any]:
    """生成数据集统计报告。"""
    instruction_counter = Counter(record["instruction"] for record in records)
    empty_counter = {field: sum(1 for record in records if not record[field].strip()) for field in FIELDS}
    output_too_short = sum(1 for record in records if 0 < len(record["output"].strip()) < 20)
    duplicate_input = len(records) - len({record["input"].strip() for record in records})
    return {
        "total": len(records),
        "instruction_unique": len(instruction_counter),
        "top_instructions": instruction_counter.most_common(top_k),
        "empty_fields": empty_counter,
        "input_length": length_stats([len(record["input"]) for record in records]),
        "output_length": length_stats([len(record["output"]) for record in records]),
        "output_too_short_lt_20_chars": output_too_short,
        "duplicate_input_count": duplicate_input,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="统计 SFT JSONL 数据集的长度、任务分布和潜在质量问题。")
    parser.add_argument("--file", required=True, help="输入 JSONL 文件。")
    parser.add_argument("--output", default=None, help="可选：将报告写入 JSON 文件。")
    parser.add_argument("--top-k", type=int, default=20, help="输出前 K 个 instruction 分布。")
    args = parser.parse_args()

    records = load_records(Path(args.file))
    report = analyze(records, args.top_k)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
