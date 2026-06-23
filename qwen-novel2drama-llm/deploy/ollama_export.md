# Ollama 部署预留

Ollama 通常使用 GGUF 模型。推荐流程：

1. 训练 LoRA。
2. 合并 LoRA 到底座模型。
3. 转换为 GGUF。
4. 编写 Modelfile。
5. `ollama create qwen-novel2drama -f Modelfile`。

本项目第一版不自动执行 GGUF 转换，避免误生成和提交大模型文件。
