"""项目级静态检查：文件结构、数据集配置和模型大文件防误提交。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    ".github/workflows/checks.yml",
    "docs/annotation_guide.md",
    "docs/data_collection.md",
    "docs/multiturn_data.md",
    "docs/qwen_ecosystem_strategy.md",
    "docs/implementation_status.md",
    "deploy/README.md",
    "deploy/gguf_export.md",
    "deploy/ollama_export.md",
    "deploy/vllm_server.md",
    "docs/data_format.md",
    "docs/dataset_plan.md",
    "docs/llamafactory_setup.md",
    "requirements.txt",
    "requirements-api.txt",
    "requirements-dev.txt",
    "requirements-train.txt",
    "requirements-windows.txt",
    ".gitignore",
    "Dockerfile",
    "datasets/train.jsonl",
    "datasets/val.jsonl",
    "datasets/raw_examples.jsonl",
    "datasets/multiturn_examples.jsonl",
    "datasets/dataset_info.json",
    "datasets/model_family_matrix.json",
    "datasets/sources.example.jsonl",
    "datasets/task_mix.json",
    "configs/model_registry.json",
    "configs/qwen2_5_1_5b_lora.yaml",
    "configs/qwen2_5_3b_lora.yaml",
    "configs/qwen2_5_7b_qlora.yaml",
    "scripts/validate_dataset.py",
    "scripts/convert_to_messages.py",
    "scripts/split_dataset.py",
    "scripts/prepare_data.py",
    "scripts/analyze_dataset.py",
    "scripts/collect_web_text.py",
    "scripts/corpus_to_sft_template.py",
    "scripts/dedupe_dataset.py",
    "scripts/check_environment.py",
    "scripts/run_checks.py",
    "scripts/sample_dataset.py",
    "scripts/train_lora.ps1",
    "scripts/train_lora.sh",
    "scripts/plan_dataset_mix.py",
    "scripts/plan_qwen_ecosystem.py",
    "scripts/inspect_model_registry.py",
    "scripts/merge_lora.ps1",
    "scripts/merge_lora.sh",
    "inference/model_utils.py",
    "inference/runtime_registry.py",
    "inference/chat.py",
    "inference/api_server.py",
    "inference/test_prompt.py",
    "inference/client_test.py",
    "prompts/system_prompt.txt",
    "prompts/novel_to_drama_prompt.txt",
    "prompts/character_prompt.txt",
    "prompts/scene_prompt.txt",
    "prompts/storyboard_prompt.txt",
    "prompts/video_prompt.txt",
    "prompts/dubbing_prompt.txt",
    "prompts/hook_twist_prompt.txt",
    "eval/eval_prompts.jsonl",
    "eval/compare_results.py",
    "eval/manual_eval_template.csv",
    "eval/run_eval.py",
    "eval/scoring_guide.md",
    "tests/test_dataset_tools.py",
]

FORBIDDEN_SUFFIXES = {".bin", ".safetensors", ".gguf", ".pt", ".pth"}
REQUIRED_DATASETS = {"novel2drama": "train.jsonl", "novel2drama_val": "val.jsonl"}
CONFLICTING_POLICY_PATTERNS = [
    re.compile(r"可以使用\s*(?:GPT|Claude|Gemini|闭源商业模型)[^。\n]*(?:训练数据|训练集)"),
    re.compile(r"(?:GPT|Claude|Gemini)[^。\n]*(?:输出|生成内容)[^。\n]*(?:可用于|可以用于|作为)[^。\n]*(?:训练数据|训练集)"),
]
NEGATED_POLICY_MARKERS = ("不要使用", "不得使用", "禁止使用", "不应使用", "不能使用")


def has_conflicting_policy(text: str) -> str | None:
    """返回文档中的冲突数据来源说明；合规的否定表述不算冲突。"""
    for pattern in CONFLICTING_POLICY_PATTERNS:
        for match in pattern.finditer(text):
            sentence_start = max(text.rfind("。", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
            sentence = text[sentence_start : match.end()]
            if any(marker in sentence for marker in NEGATED_POLICY_MARKERS):
                continue
            return match.group(0)
    return None


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

    for doc_path in [project_root / "README.md", *sorted((project_root / "docs").glob("*.md"))]:
        if not doc_path.exists():
            continue
        text = doc_path.read_text(encoding="utf-8")
        conflicting_policy = has_conflicting_policy(text)
        if conflicting_policy:
            errors.append(f"文档 {doc_path.relative_to(project_root)} 包含冲突的数据来源说明：{conflicting_policy}")

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
