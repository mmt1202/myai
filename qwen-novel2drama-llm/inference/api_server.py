"""FastAPI 本地模型服务。"""
from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from chat import generate, load_model
from fastapi import FastAPI, HTTPException
from model_utils import generate_text, load_model, load_system_prompt
from pydantic import BaseModel, Field

app = FastAPI(title="qwen-novel2drama-llm API")
TOKENIZER: Any | None = None
MODEL: Any | None = None
SYSTEM_PROMPT = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户提示词。")
    max_new_tokens: int = Field(1024, ge=1, le=8192, description="最大生成 token 数。")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="采样温度。")


class GenerateResponse(BaseModel):
    result: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate_api(request: GenerateRequest) -> GenerateResponse:
    if TOKENIZER is None or MODEL is None:
        raise HTTPException(status_code=503, detail="模型尚未加载完成。")
    try:
        result = generate_text(
            TOKENIZER,
            MODEL,
            request.prompt,
            request.max_new_tokens,
            request.temperature,
            SYSTEM_PROMPT,
        )
    except Exception as exc:  # noqa: BLE001 - API 需要返回清晰错误
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc
    return GenerateResponse(result=result)


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 novel2drama FastAPI 本地服务。")
    parser.add_argument("--model-path", required=True, help="底座模型或已合并模型路径。")
    parser.add_argument("--adapter-path", default=None, help="可选 LoRA adapter 路径。")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="系统提示词文件路径。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址。")
    parser.add_argument("--port", type=int, default=8000, help="监听端口。")
    args = parser.parse_args()
    global TOKENIZER, MODEL, SYSTEM_PROMPT
    SYSTEM_PROMPT = load_system_prompt(args.system_prompt_file)
    TOKENIZER, MODEL, _ = load_model(args.model_path, args.adapter_path)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
