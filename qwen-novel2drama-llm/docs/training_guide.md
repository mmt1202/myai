# 训练流程指南

1. 准备 Python 环境并安装依赖。
2. 准备 `datasets/train.jsonl` 和 `datasets/val.jsonl`。
3. 运行数据校验。
4. 安装 LLaMA-Factory。
5. 选择配置文件。
6. 运行 `scripts/train_lora.ps1` 或 `scripts/train_lora.sh`。
7. 训练完成后在 `saves/` 查看 adapter。
8. 可选：使用 merge 脚本导出合并模型到 `outputs/`。

第一版建议先使用 `configs/qwen2_5_1_5b_lora.yaml` 跑通流程。
