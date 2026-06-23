# vLLM 部署预留

后续如需高并发服务，可使用 vLLM 的 OpenAI-compatible API。

示例：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /models/merged-qwen-novel2drama \
  --served-model-name qwen-novel2drama \
  --host 0.0.0.0 \
  --port 8000
```

注意：vLLM 部署通常建议使用已合并模型，而不是训练中的 LoRA adapter 目录。
