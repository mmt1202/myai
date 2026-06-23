"""将 Alpaca instruction/input/output JSONL 转换为 messages JSONL。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SYSTEM = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"


def build_user_content(instruction: str, input_text: str) -> str:
    """组合 instruction 和 input，形成用户消息。"""
    if input_text.strip():
        return f"{instruction.strip()}\n\n输入：\n{input_text.strip()}"
    return instruction.strip()


def convert_record(record: dict[str, Any], system_prompt: str) -> dict[str, Any] | None:
    """转换单条 Alpaca 样本；output 为空时返回 None。"""
    instruction = str(record.get("instruction", "")).strip()
    input_text = str(record.get("input", "")).strip()
    output = str(record.get("output", "")).strip()
    if not instruction or not output:
        return None
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_content(instruction, input_text)},
            {"role": "assistant", "content": output},
        ]
    }


def convert_file(input_path: Path, output_path: Path, system_prompt: str) -> tuple[int, int]:
    """转换文件，返回读取数量和写入数量。"""
    total = 0
    written = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as reader, output_path.open("w", encoding="utf-8") as writer:
        for line in reader:
            if not line.strip():
                continue
            total += 1
            record = json.loads(line)
            converted = convert_record(record, system_prompt)
            if converted is None:
                continue
            writer.write(json.dumps(converted, ensure_ascii=False) + "\n")
            written += 1
    return total, written


def main() -> int:
    parser = argparse.ArgumentParser(description="将 instruction/input/output JSONL 转换为 messages JSONL。")
    parser.add_argument("--input", required=True, help="输入 Alpaca JSONL。")
    parser.add_argument("--output", required=True, help="输出 messages JSONL。")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="系统提示词文件。")
    args = parser.parse_args()
    system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8").strip() if args.system_prompt_file else DEFAULT_SYSTEM
    total, written = convert_file(Path(args.input), Path(args.output), system_prompt)
    print(f"转换完成：读取 {total} 条，写入 {written} 条，输出：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
