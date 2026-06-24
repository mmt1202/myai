# 部署说明

部署阶段默认使用**已合并模型**或本地 Hugging Face 模型目录，不会自动下载模型权重，也不会把权重提交到 Git。

## 推荐上线流程

1. 训练 LoRA / QLoRA，确认验证集和人工评估通过。
2. 使用 `scripts/merge_lora.sh` 或 `scripts/merge_lora.ps1` 合并 adapter。
3. 将合并后的模型放在 `.gitignore` 已排除的目录，例如 `models/`、`outputs/` 或独立模型盘。
4. 选择部署方式：
   - 本地 FastAPI：适合开发调试、低并发内网服务。
   - Docker FastAPI：适合固定依赖和轻量服务封装。
   - vLLM：适合高并发 OpenAI-compatible API。
   - Ollama / GGUF：适合本地桌面、边缘设备或 CPU/量化推理。
5. 业务侧记录 prompt 模板版本、模型版本、生成结果和人工评分，方便后续回流训练。

## Docker 本地 API 镜像

```bash
docker build -t qwen-novel2drama-api .
docker run --rm -p 8000:8000 -v /path/to/models:/models qwen-novel2drama-api \
  python inference/api_server.py \
  --model-path /models/merged-qwen-novel2drama \
  --system-prompt-file prompts/system_prompt.txt \
  --host 0.0.0.0 \
  --port 8000
```

GPU 推理需要使用带 CUDA 的基础镜像，并按你的 CUDA/PyTorch 版本调整 `requirements-api.txt` 和基础镜像。

## 健康检查与试调用

服务启动后可以先访问：

```bash
curl http://127.0.0.1:8000/health
```

再发送一次短文本生成请求：

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"请把小说片段改成短剧大纲：女主在订婚宴被背叛。","max_new_tokens":256,"temperature":0.7}'
```

## 不提交模型权重

模型目录、LoRA 输出、GGUF 文件、合并模型和评测输出均不应提交到 Git。提交前建议运行：

```bash
python scripts/check_project.py --project-root .
```
