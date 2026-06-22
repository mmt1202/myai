#!/usr/bin/env bash
set -euo pipefail
CONFIG_PATH="${1:-configs/qwen2_5_1_5b_lora.yaml}"
if ! command -v llamafactory-cli >/dev/null 2>&1; then
  echo "未找到 llamafactory-cli。请先安装 LLaMA-Factory，并确认命令已加入 PATH。" >&2
  echo "参考：https://github.com/hiyouga/LLaMA-Factory" >&2
  exit 1
fi
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
llamafactory-cli train "$CONFIG_PATH"
