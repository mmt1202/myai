"""批量运行内置测试提示词。"""
from __future__ import annotations

import argparse
from chat import generate, load_model

TEST_PROMPTS = [
    "请把小说片段改成短剧大纲：女主在订婚宴被背叛，转身联手神秘投资人复仇。",
    "请生成竖屏分镜：雨夜别墅外，女主被赶出家门，男主递出名片。",
    "请生成角色设定：冷静克制的豪门掌权人男主。",
    "请生成 AI 视频提示词：女主在宴会上公开证据，全场震惊。",
    "请生成配音台词：女主发现背叛后当众反击。",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 novel2drama 内置提示词测试。")
    parser.add_argument("--model-path", required=True, help="底座模型或已合并模型路径。")
    parser.add_argument("--adapter-path", default=None, help="可选 LoRA adapter 路径。")
    parser.add_argument("--max-new-tokens", type=int, default=1024, help="最大生成 token 数。")
    parser.add_argument("--temperature", type=float, default=0.7, help="采样温度。")
    args = parser.parse_args()
    tokenizer, model, _ = load_model(args.model_path, args.adapter_path)
    for index, prompt in enumerate(TEST_PROMPTS, start=1):
        print(f"\n===== 测试 {index} =====")
        print("Prompt:", prompt)
        print("Response:", generate(tokenizer, model, prompt, args.max_new_tokens, args.temperature))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
