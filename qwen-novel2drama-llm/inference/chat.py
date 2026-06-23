"""使用 transformers 进行 Qwen 本地交互式推理。"""
from __future__ import annotations

import argparse

from model_utils import generate_text, load_model, load_system_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen novel2drama 命令行聊天推理。")
    parser.add_argument("--model-path", required=True, help="底座模型或已合并模型路径。")
    parser.add_argument("--adapter-path", default=None, help="可选 LoRA adapter 路径。")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="系统提示词文件路径。")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="最大生成 token 数。")
    parser.add_argument("--temperature", type=float, default=0.7, help="采样温度。")
    args = parser.parse_args()
    try:
        system_prompt = load_system_prompt(args.system_prompt_file)
        tokenizer, model, _ = load_model(args.model_path, args.adapter_path)
        print("输入 exit 或 quit 退出。")
        while True:
            prompt = input("\n用户> ").strip()
            if prompt.lower() in {"exit", "quit"}:
                break
            if not prompt:
                continue
            result = generate_text(tokenizer, model, prompt, args.max_new_tokens, args.temperature, system_prompt)
            print("\n模型>", result)
    except Exception as exc:  # noqa: BLE001 - 命令行入口需要给用户清晰错误
        print(f"推理失败：{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
