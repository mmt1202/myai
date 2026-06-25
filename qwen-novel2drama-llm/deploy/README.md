# 部署说明

第一版部署目录只提供模板，不会自动下载模型权重。

## Docker 本地 API 镜像

```bash
docker build -t qwen-novel2drama-api .
docker run --rm -p 8000:8000 -v /path/to/models:/models qwen-novel2drama-api \
  python inference/api_server.py --model-path /models/Qwen2.5-1.5B-Instruct --host 0.0.0.0 --port 8000
```

GPU 推理需要使用带 CUDA 的基础镜像，并按你的 CUDA/PyTorch 版本调整依赖。

## 不提交模型权重

模型目录、LoRA 输出、GGUF 文件和合并模型均不应提交到 Git。
