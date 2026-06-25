"""FastAPI local model service."""
from __future__ import annotations

import argparse
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from model_utils import generate_text, load_model, load_system_prompt
from model_version_registry import resolve_model_paths
from pydantic import BaseModel, Field

app = FastAPI(title="qwen-novel2drama-llm API")
TOKENIZER: Any | None = None
MODEL: Any | None = None
SYSTEM_PROMPT = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"
ACTIVE_MODEL_VERSION: str | None = None
ACTIVE_MODEL_PATH: str | None = None


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_new_tokens: int = Field(1024, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    result: str
    model_version: str | None = None


@app.get("/health")
def health() -> dict[str, str | None]:
    return {"status": "ok", "model_version": ACTIVE_MODEL_VERSION, "model_path": ACTIVE_MODEL_PATH}


@app.post("/generate", response_model=GenerateResponse)
def generate_api(request: GenerateRequest) -> GenerateResponse:
    if TOKENIZER is None or MODEL is None:
        raise HTTPException(status_code=503, detail="model is not loaded")
    try:
        result = generate_text(TOKENIZER, MODEL, request.prompt, request.max_new_tokens, request.temperature, SYSTEM_PROMPT)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"generation failed: {exc}") from exc
    return GenerateResponse(result=result, model_version=ACTIVE_MODEL_VERSION)


def resolve_startup_model(args: argparse.Namespace) -> tuple[str, str | None, str | None]:
    if args.model_path:
        return args.model_path, args.adapter_path, None
    model_path, adapter_path, item = resolve_model_paths(args.model_versions, args.model_version)
    return model_path, args.adapter_path if args.adapter_path is not None else adapter_path, item.get("version")


def main() -> int:
    parser = argparse.ArgumentParser(description="Start novel2drama FastAPI local service.")
    parser.add_argument("--model-path", default=None, help="Base or merged model path. If omitted, use model version registry.")
    parser.add_argument("--adapter-path", default=None, help="Optional LoRA adapter path.")
    parser.add_argument("--model-versions", default="configs/model_versions.json", help="Model version registry path.")
    parser.add_argument("--model-version", default=None, help="Model version to load. If omitted, use active_version.")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="System prompt file path.")
    parser.add_argument("--host", default="127.0.0.1", help="Host.")
    parser.add_argument("--port", type=int, default=8000, help="Port.")
    args = parser.parse_args()

    global TOKENIZER, MODEL, SYSTEM_PROMPT, ACTIVE_MODEL_VERSION, ACTIVE_MODEL_PATH
    try:
        model_path, adapter_path, version = resolve_startup_model(args)
        SYSTEM_PROMPT = load_system_prompt(args.system_prompt_file)
        TOKENIZER, MODEL, _ = load_model(model_path, adapter_path)
        ACTIVE_MODEL_VERSION = version
        ACTIVE_MODEL_PATH = model_path
    except Exception as exc:  # noqa: BLE001
        print(f"service startup failed: {exc}")
        return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
