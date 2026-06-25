# P0 文本 LoRA 训练闭环 Runbook

本文档用于把 P0 文本模型从脚手架推进到可复现训练闭环。

## 1. 训练前检查

```bash
python scripts/check_environment.py
python scripts/check_project.py --project-root .
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
python scripts/analyze_dataset.py --file datasets/train.jsonl --output outputs/train_report.json
```

## 2. 生成训练运行计划

```bash
python scripts/plan_training_run.py --config configs/qwen2_5_1_5b_lora.yaml --run-name qwen2_5_1_5b_lora_v1
```

输出位置默认是：

```text
outputs/training_runs/qwen2_5_1_5b_lora_v1.json
```

manifest 会记录：

- 训练配置路径和 sha256。
- 底座模型名称。
- 训练集和验证集路径、行数、sha256。
- 输出目录。
- Linux/macOS 与 Windows 的训练命令。
- LoRA 合并命令。

## 3. 开始训练

Linux/macOS：

```bash
bash scripts/train_lora.sh configs/qwen2_5_1_5b_lora.yaml
```

Windows PowerShell：

```powershell
.\scripts\train_lora.ps1 -Config configs/qwen2_5_1_5b_lora.yaml
```

## 4. 合并 LoRA

Linux/macOS：

```bash
bash scripts/merge_lora.sh Qwen/Qwen2.5-1.5B-Instruct saves/qwen2_5_1_5b_lora models/qwen2_5_1_5b_lora_v1-merged
```

Windows PowerShell：

```powershell
.\scripts\merge_lora.ps1 -BaseModel Qwen/Qwen2.5-1.5B-Instruct -AdapterPath saves/qwen2_5_1_5b_lora -OutputPath models/qwen2_5_1_5b_lora_v1-merged
```

## 5. 本地推理验证

```bash
python inference/chat.py --model-path models/qwen2_5_1_5b_lora_v1-merged --system-prompt-file prompts/system_prompt.txt
```

## 6. API 验证

```bash
python inference/api_server.py --model-path models/qwen2_5_1_5b_lora_v1-merged --system-prompt-file prompts/system_prompt.txt
python inference/client_test.py
```

## 7. 固定评测

```bash
python eval/run_eval.py --model-path models/qwen2_5_1_5b_lora_v1-merged --prompts eval/eval_prompts.jsonl --output eval/qwen2_5_1_5b_lora_v1_results.jsonl
```

如果你保留了训练前的 base 结果，可以对比：

```bash
python eval/compare_results.py --base eval/base_results.jsonl --candidate eval/qwen2_5_1_5b_lora_v1_results.jsonl --output eval/qwen2_5_1_5b_lora_v1_compare.csv
```

## 8. 不要提交权重

不要把以下文件提交到 Git：

- `models/`
- `saves/`
- `outputs/`
- `.safetensors`
- `.bin`
- `.gguf`
- `.pt`
- `.pth`
