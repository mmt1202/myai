#!/usr/bin/env bash
set -euo pipefail
# 允许从任意目录调用脚本，实际执行目录固定为项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
CONFIG_PATH="${1:-configs/qwen2_5_1_5b_lora.yaml}"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "配置文件不存在：$CONFIG_PATH" >&2
  exit 1
fi
if ! command -v llamafactory-cli >/dev/null 2>&1; then
  echo "未找到 llamafactory-cli。请先安装 LLaMA-Factory，并确认命令已加入 PATH。" >&2
  echo "参考：https://github.com/hiyouga/LLaMA-Factory" >&2
  exit 1
fi
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
llamafactory-cli train "$CONFIG_PATH"
