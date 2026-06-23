"""使用 transformers 进行 Qwen 本地交互式推理。"""
from __future__ import annotations

import argparse

from model_utils import generate_text, load_model, load_system_prompt
SYSTEM_PROMPT = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"


def load_model(model_path: str, adapter_path: str | None = None) -> tuple[Any, Any, torch.device]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cpu":
        print("提示：当前未检测到 GPU，将使用 CPU 推理，速度可能很慢。")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        device_map="auto" if device.type == "cuda" else None,
        trust_remote_code=True,
    )
    if device.type == "cpu":
        model.to(device)
    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return tokenizer, model, device


def generate(tokenizer: Any, model: Any, prompt: str, max_new_tokens: int, temperature: float) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            eos_token_id=tokenizer.eos_token_id,
        )
    new_ids = output_ids[0][inputs.input_ids.shape[-1] :]
    return tokenizer.decode(new_ids, skip_special_tokens=True).strip()


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
