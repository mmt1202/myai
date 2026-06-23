"""Qwen 模型加载与生成的共享工具。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_SYSTEM_PROMPT = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"


def load_system_prompt(system_prompt_file: str | None = None) -> str:
    """读取系统提示词文件；未提供时使用内置默认提示词。"""
    if not system_prompt_file:
        return DEFAULT_SYSTEM_PROMPT
    path = Path(system_prompt_file)
    if not path.exists():
        raise FileNotFoundError(f"系统提示词文件不存在：{path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"系统提示词文件为空：{path}")
    return text


def load_model(model_path: str, adapter_path: str | None = None) -> tuple[Any, Any, torch.device]:
    """加载 Qwen 底座模型，并可选加载 LoRA adapter。"""
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


def generate_text(
    tokenizer: Any,
    model: Any,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> str:
    """使用 Qwen chat template 生成文本。"""
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
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
