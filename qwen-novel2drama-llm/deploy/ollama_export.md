# Ollama 部署指南

Ollama 通常使用 GGUF 模型。推荐流程：训练 LoRA -> 合并 LoRA -> 转换 GGUF -> 编写 Modelfile -> `ollama create`。

## 示例 Modelfile

```text
FROM /path/to/models/qwen-novel2drama-q4_k_m.gguf

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM """
你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家，擅长把小说内容改编成适合竖屏短剧和 AI 视频生成的结构化内容。
"""
```

创建模型：

```bash
ollama create qwen-novel2drama -f Modelfile
```

试调用：

```bash
ollama run qwen-novel2drama "请把小说片段改成 60 秒竖屏短剧分镜：女主在订婚宴被背叛。"
```

## 版本记录建议

- 在 Modelfile 旁边保存底座模型、adapter 路径、合并脚本参数和 GGUF 量化类型。
- 业务系统记录 Ollama 模型名和 Modelfile 版本。
- 如果后续换量化等级或重新合并 adapter，使用新的模型名或版本号，避免覆盖线上结果。

本项目不自动执行 GGUF 转换，避免误生成和提交大模型文件。
