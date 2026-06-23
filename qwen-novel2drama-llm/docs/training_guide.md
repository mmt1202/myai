# 训练流程指南

## 1. 环境准备

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. 安装 LLaMA-Factory

训练和 LoRA 合并依赖 `llamafactory-cli`。请按 LLaMA-Factory 官方文档安装，并确认：

```bash
llamafactory-cli --help
```

## 3. 项目静态检查

```bash
python scripts/check_project.py --project-root .
```

该命令会检查必要文件、`dataset_info.json`、训练配置中的 `eval_dataset`，以及是否误放入模型权重文件。

## 4. 数据准备

```bash
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
```

如果要从小说 TXT 生成待标注模板：

```bash
python scripts/prepare_data.py --input-dir raw_novels --output datasets/raw_examples.jsonl --chunk-size 1200
```

## 5. 选择模型

- 第一次跑通：`configs/qwen2_5_1_5b_lora.yaml`
- 8GB-12GB：`configs/qwen2_5_3b_lora.yaml`
- 16GB-24GB：`configs/qwen2_5_7b_qlora.yaml`

## 6. 数据质量检查

```bash
python scripts/analyze_dataset.py --file datasets/train.jsonl --output outputs/train_report.json
python scripts/dedupe_dataset.py --input datasets/train.jsonl --output outputs/train.dedup.jsonl
python scripts/sample_dataset.py --input datasets/train.jsonl --output outputs/sample_review.jsonl --size 20
```

## 7. 运行轻量测试

```bash
python -m unittest discover -s tests
```

该测试只覆盖数据工具和项目检查，不会下载模型，也不会启动训练。

推荐训练前直接运行完整轻量检查：

```bash
python scripts/run_checks.py --project-root .
```

## 8. 开始训练

Windows：

```powershell
.\scripts\train_lora.ps1 -Config configs/qwen2_5_1_5b_lora.yaml
```

Linux/macOS：

```bash
bash scripts/train_lora.sh configs/qwen2_5_1_5b_lora.yaml
```

## 9. 训练后检查

关注：

- loss 是否正常下降。
- 是否频繁 OOM。
- 生成结果是否结构化。
- 是否出现复读、乱码、格式漂移。

## 10. 合并/导出 LoRA

```bash
bash scripts/merge_lora.sh Qwen/Qwen2.5-1.5B-Instruct saves/qwen2_5_1_5b_lora outputs/merged-qwen-novel2drama
```

不要把 `saves/`、`outputs/`、模型权重提交到 Git。
