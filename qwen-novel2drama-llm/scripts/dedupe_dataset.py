"""对 instruction/input/output JSONL 数据集去重。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def record_key(record: dict[str, Any], mode: str) -> str:
    """生成去重 key。"""
    if mode == "input":
        return str(record.get("input", "")).strip()
    if mode == "instruction_input":
        return f"{record.get('instruction', '')}\n{record.get('input', '')}".strip()
    return json.dumps(
        {
            "instruction": record.get("instruction", ""),
            "input": record.get("input", ""),
            "output": record.get("output", ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def dedupe(input_path: Path, output_path: Path, mode: str) -> tuple[int, int]:
    """读取 JSONL 去重，返回原始数量和保留数量。"""
    seen: set[str] = set()
    total = 0
    kept = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as reader, output_path.open("w", encoding="utf-8") as writer:
        for line in reader:
            if not line.strip():
                continue
            total += 1
            record = json.loads(line)
            key = record_key(record, mode)
            if key in seen:
                continue
            seen.add(key)
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
    return total, kept


def main() -> int:
    parser = argparse.ArgumentParser(description="对 JSONL 数据集去重。")
    parser.add_argument("--input", required=True, help="输入 JSONL 文件。")
    parser.add_argument("--output", required=True, help="输出去重后的 JSONL 文件。")
    parser.add_argument(
        "--mode",
        choices=("input", "instruction_input", "full"),
        default="instruction_input",
        help="去重模式：input、instruction_input 或 full。",
    )
    args = parser.parse_args()
    total, kept = dedupe(Path(args.input), Path(args.output), args.mode)
    print(f"去重完成：原始 {total} 条，保留 {kept} 条，删除 {total - kept} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
