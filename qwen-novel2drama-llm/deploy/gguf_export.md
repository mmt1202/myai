# GGUF 导出指南

GGUF 适合 llama.cpp、Ollama 和部分本地桌面推理工具。建议先合并 LoRA，再转换和量化。

## 前置条件

- 已有底座模型和 LoRA adapter。
- 已运行合并脚本生成完整 Hugging Face 模型目录。
- 已安装与你的模型兼容的 `llama.cpp` 转换工具。

## 参考流程

```bash
bash scripts/merge_lora.sh \
  Qwen/Qwen2.5-1.5B-Instruct \
  saves/qwen2_5_1_5b_lora \
  models/merged-qwen-novel2drama
```

然后在 `llama.cpp` 环境中转换：

```bash
python convert_hf_to_gguf.py \
  /path/to/models/merged-qwen-novel2drama \
  --outfile /path/to/models/qwen-novel2drama-f16.gguf
```

按目标设备量化，例如：

```bash
./llama-quantize \
  /path/to/models/qwen-novel2drama-f16.gguf \
  /path/to/models/qwen-novel2drama-q4_k_m.gguf \
  Q4_K_M
```

## 校验建议

- 用 3-5 条 `eval/eval_prompts.jsonl` 中的提示词检查输出结构。
- 对比量化前后是否仍能生成大纲、角色、场景、分镜和视频提示词。
- 如果出现重复、乱码或格式漂移，优先尝试更高精度量化。

不要提交 `.gguf` 文件到 Git；项目检查会拦截此类权重文件。
