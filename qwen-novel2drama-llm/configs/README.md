# 训练配置说明

- `qwen2_5_1_5b_lora.yaml`：低显存入门，建议第一版先跑通。
- `qwen2_5_3b_lora.yaml`：8GB-12GB 显存尝试，效果与成本平衡。
- `qwen2_5_7b_qlora.yaml`：16GB-24GB 显存尝试，使用 4bit QLoRA。

所有配置均面向 LLaMA-Factory，默认数据集名称为 `novel2drama`。
