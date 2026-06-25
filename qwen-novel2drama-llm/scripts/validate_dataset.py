"""校验 novel2drama JSONL 数据集。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = ("instruction", "input", "output")


def validate_record(record: Any, line_no: int) -> list[str]:
    """校验单条样本，返回错误列表。"""
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"第 {line_no} 行不是 JSON 对象"]
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"第 {line_no} 行缺少字段：{field}")
        elif not isinstance(record[field], str) or not record[field].strip():
            errors.append(f"第 {line_no} 行字段为空或不是字符串：{field}")
    return errors


def validate_file(file_path: Path) -> int:
    if not file_path.exists():
        print(f"错误：文件不存在：{file_path}", file=sys.stderr)
        return 1

    total = 0
    valid = 0
    errors: list[str] = []
    with file_path.open("r", encoding="utf-8") as reader:
        for line_no, line in enumerate(reader, start=1):
            total += 1
            text = line.strip()
            if not text:
                errors.append(f"第 {line_no} 行为空行")
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"第 {line_no} 行 JSON 解析失败：{exc}")
                continue
            row_errors = validate_record(record, line_no)
            if row_errors:
                errors.extend(row_errors)
            else:
                valid += 1

    print(f"总行数：{total}")
    print(f"有效样本数：{valid}")
    print(f"错误数量：{len(errors)}")
    for error in errors:
        print(f"错误：{error}", file=sys.stderr)

    if errors:
        return 1
    print("数据校验通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 instruction/input/output JSONL 数据集。")
    parser.add_argument("--file", required=True, help="待校验的 JSONL 文件路径。")
    args = parser.parse_args()
    return validate_file(Path(args.file))


if __name__ == "__main__":
    raise SystemExit(main())
