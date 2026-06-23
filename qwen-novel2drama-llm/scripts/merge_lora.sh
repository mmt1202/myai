#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
BASE_MODEL="${1:-}"
ADAPTER_PATH="${2:-}"
OUTPUT_PATH="${3:-}"
if [[ -z "$BASE_MODEL" || -z "$ADAPTER_PATH" || -z "$OUTPUT_PATH" ]]; then
  echo "用法：bash scripts/merge_lora.sh <base_model> <adapter_path> <output_path>" >&2
  exit 1
fi
if ! command -v llamafactory-cli >/dev/null 2>&1; then
  echo "未找到 llamafactory-cli。请先安装 LLaMA-Factory。" >&2
  exit 1
fi
llamafactory-cli export --model_name_or_path "$BASE_MODEL" --adapter_name_or_path "$ADAPTER_PATH" --template qwen --finetuning_type lora --export_dir "$OUTPUT_PATH" --export_size 2 --export_legacy_format false
