"""从 txt 小说文件生成待人工标注的 JSONL 模板。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_INSTRUCTION = "请把下面小说片段改编成一集 60 秒竖屏 AI 短剧分镜脚本"


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """优先按段落聚合，超过长度时再切块。"""
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(paragraph[i : i + chunk_size] for i in range(0, len(paragraph), chunk_size))
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


def main() -> int:
    parser = argparse.ArgumentParser(description="读取 txt 小说文件并生成 instruction/input/output JSONL 模板。")
    parser.add_argument("--input-dir", required=True, help="包含 txt 小说文件的目录。")
    parser.add_argument("--output", required=True, help="输出 JSONL 文件路径。")
    parser.add_argument("--chunk-size", type=int, default=1200, help="每个片段最大字符数，默认 1200。")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"输入目录不存在：{input_dir}")
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size 必须大于 0。")

    records: list[dict[str, str]] = []
    for txt_file in sorted(input_dir.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        for chunk in chunk_text(text, args.chunk_size):
            records.append({"instruction": DEFAULT_INSTRUCTION, "input": chunk, "output": ""})

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as writer:
        for record in records:
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"已生成模板样本：{len(records)} 条，输出：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
