# GGUF 导出预留

GGUF 转换依赖具体模型结构、转换工具和量化策略。建议在合并 LoRA 后单独执行转换，并将输出放到 `.gitignore` 已排除的目录，例如 `outputs/` 或 `models/`。

不要提交 `.gguf` 文件到 Git。
