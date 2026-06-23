"""项目级静态检查：文件结构、数据集配置和模型大文件防误提交。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "requirements.txt",
    ".gitignore",
    "datasets/train.jsonl",
    "datasets/val.jsonl",
    "datasets/raw_examples.jsonl",
    "datasets/dataset_info.json",
    "configs/qwen2_5_1_5b_lora.yaml",
    "configs/qwen2_5_3b_lora.yaml",
    "configs/qwen2_5_7b_qlora.yaml",
    "scripts/validate_dataset.py",
    "scripts/split_dataset.py",
    "scripts/prepare_data.py",
    "scripts/train_lora.ps1",
    "scripts/train_lora.sh",
    "scripts/merge_lora.ps1",
    "scripts/merge_lora.sh",
    "inference/model_utils.py",
    "inference/chat.py",
    "inference/api_server.py",
    "inference/test_prompt.py",
    "inference/client_test.py",
    "eval/eval_prompts.jsonl",
    "eval/run_eval.py",
    "tests/test_dataset_tools.py",
]

FORBIDDEN_SUFFIXES = {".bin", ".safetensors", ".gguf", ".pt", ".pth"}
REQUIRED_DATASETS = {"novel2drama": "train.jsonl", "novel2drama_val": "val.jsonl"}


def collect_errors(project_root: Path) -> list[str]:
    """收集项目静态检查错误。"""
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (project_root / relative_path).exists():
            errors.append(f"缺少必要文件：{relative_path}")

    dataset_info_path = project_root / "datasets" / "dataset_info.json"
    if dataset_info_path.exists():
        try:
            dataset_info = json.loads(dataset_info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"dataset_info.json 不是合法 JSON：{exc}")
        else:
            for dataset_name, file_name in REQUIRED_DATASETS.items():
                item = dataset_info.get(dataset_name)
                if not isinstance(item, dict):
                    errors.append(f"dataset_info.json 缺少数据集：{dataset_name}")
                    continue
                if item.get("file_name") != file_name:
                    errors.append(f"数据集 {dataset_name} 的 file_name 应为 {file_name}")
                columns = item.get("columns", {})
                expected_columns = {"prompt": "instruction", "query": "input", "response": "output"}
                if columns != expected_columns:
                    errors.append(f"数据集 {dataset_name} 字段映射不正确：{columns}")

    for path in project_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"发现不应提交的模型/权重文件：{path.relative_to(project_root)}")

    for config_path in (project_root / "configs").glob("*.yaml"):
        text = config_path.read_text(encoding="utf-8")
        for required in ("stage: sft", "finetuning_type: lora", "template: qwen", "dataset: novel2drama"):
            if required not in text:
                errors.append(f"配置 {config_path.name} 缺少：{required}")
        if "eval_dataset: novel2drama_val" not in text:
            errors.append(f"配置 {config_path.name} 未显式指定 eval_dataset: novel2drama_val")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 qwen-novel2drama-llm 项目结构和关键配置。")
    parser.add_argument("--project-root", default=".", help="项目根目录，默认当前目录。")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    errors = collect_errors(project_root)
    if errors:
        print("项目检查失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("项目检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
