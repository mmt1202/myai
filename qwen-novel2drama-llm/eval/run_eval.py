"""运行本地模型评估并输出 JSONL 结果。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "inference"))
from model_utils import generate_text, load_model, load_system_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="读取 eval_prompts.jsonl 并生成 eval/results.jsonl。")
    parser.add_argument("--model-path", required=True, help="底座模型或已合并模型路径。")
    parser.add_argument("--adapter-path", default=None, help="可选 LoRA adapter 路径。")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="系统提示词文件路径。")
    parser.add_argument("--input", default="eval/eval_prompts.jsonl", help="评估 prompt JSONL。")
    parser.add_argument("--output", default="eval/results.jsonl", help="输出结果 JSONL。")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="最大生成 token 数。")
    parser.add_argument("--temperature", type=float, default=0.7, help="采样温度。")
    args = parser.parse_args()

    system_prompt = load_system_prompt(args.system_prompt_file)
    tokenizer, model, _ = load_model(args.model_path, args.adapter_path)
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8") as reader, output_path.open("w", encoding="utf-8") as writer:
        for line in reader:
            if not line.strip():
                continue
            prompt = json.loads(line)["prompt"]
            response = generate_text(tokenizer, model, prompt, args.max_new_tokens, args.temperature, system_prompt)
            record = {"prompt": prompt, "response": response, "created_at": datetime.now(timezone.utc).isoformat()}
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"评估完成，结果已写入：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
