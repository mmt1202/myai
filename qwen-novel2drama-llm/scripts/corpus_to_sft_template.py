"""将 raw_corpus.jsonl 转换为待人工标注的 SFT JSONL 模板。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_INSTRUCTION = "请把下面小说片段改编成一集 60 秒竖屏 AI 短剧分镜脚本"


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """按字符长度切分长文本，并尽量保留段落边界。"""
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(paragraph[index : index + chunk_size] for index in range(0, len(paragraph), chunk_size))
            continue
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def convert_corpus(input_path: Path, output_path: Path, instruction: str, chunk_size: int) -> int:
    """转换 raw corpus JSONL 到 instruction/input/output 模板。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as reader, output_path.open("w", encoding="utf-8") as writer:
        for line_no, line in enumerate(reader, start=1):
            if not line.strip():
                continue
            item: dict[str, Any] = json.loads(line)
            text = str(item.get("text", "")).strip()
            if not text:
                raise ValueError(f"第 {line_no} 行缺少 text 字段")
            for chunk in chunk_text(text, chunk_size):
                record = {
                    "instruction": instruction,
                    "input": chunk,
                    "output": "",
                    "source_url": item.get("url", ""),
                    "source_name": item.get("source_name", ""),
                    "license": item.get("license", ""),
                }
                writer.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="将采集到的 raw_corpus.jsonl 转换为待人工标注 SFT 模板。")
    parser.add_argument("--input", required=True, help="输入 raw corpus JSONL，字段包含 text/url/license。")
    parser.add_argument("--output", required=True, help="输出 SFT 模板 JSONL。")
    parser.add_argument("--chunk-size", type=int, default=1200, help="切片最大字符数，默认 1200。")
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION, help="写入每条样本的默认 instruction。")
    args = parser.parse_args()
    count = convert_corpus(Path(args.input), Path(args.output), args.instruction, args.chunk_size)
    print(f"转换完成：生成 {count} 条待标注样本，输出：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
