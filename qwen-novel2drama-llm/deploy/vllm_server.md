# vLLM 部署指南

vLLM 适合高并发推理和 OpenAI-compatible API。生产部署建议使用已合并模型目录，而不是训练中的 LoRA adapter 目录。

## 启动示例

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /models/merged-qwen-novel2drama \
  --served-model-name qwen-novel2drama \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --max-model-len 4096
```

## OpenAI-compatible 调用示例

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"qwen-novel2drama",
    "messages":[
      {"role":"system","content":"你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"},
      {"role":"user","content":"请把小说片段改成短剧大纲：女主在订婚宴被背叛。"}
    ],
    "temperature":0.7,
    "max_tokens":512
  }'
```

## 上线检查

- 使用 `eval/eval_prompts.jsonl` 做固定样例回归。
- 检查分镜、角色、场景、视频提示词是否仍保持结构化输出。
- 记录 `served-model-name`、合并模型目录、启动参数和 prompt 模板版本。
- 高并发前先压测显存占用、首 token 延迟和长输出稳定性。
