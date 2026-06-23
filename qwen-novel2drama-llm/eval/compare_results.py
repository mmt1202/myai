"""对比两份 eval/results.jsonl，生成便于人工评估的 CSV。"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    """按 prompt 读取评估结果。"""
    results: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if not line.strip():
                continue
            item = json.loads(line)
            prompt = str(item.get("prompt", "")).strip()
            if prompt:
                results[prompt] = item
    return results


def compare(base_path: Path, candidate_path: Path, output_path: Path) -> int:
    """对齐 prompt 并输出对比 CSV，返回对齐样本数。"""
    base_results = load_results(base_path)
    candidate_results = load_results(candidate_path)
    prompts = sorted(set(base_results) & set(candidate_results))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as writer_file:
        writer = csv.DictWriter(
            writer_file,
            fieldnames=[
                "id",
                "prompt",
                "base_response",
                "candidate_response",
                "base_length",
                "candidate_length",
                "preferred",
                "score_delta",
                "notes",
            ],
        )
        writer.writeheader()
        for index, prompt in enumerate(prompts, start=1):
            base_response = str(base_results[prompt].get("response", ""))
            candidate_response = str(candidate_results[prompt].get("response", ""))
            writer.writerow(
                {
                    "id": index,
                    "prompt": prompt,
                    "base_response": base_response,
                    "candidate_response": candidate_response,
                    "base_length": len(base_response),
                    "candidate_length": len(candidate_response),
                    "preferred": "",
                    "score_delta": "",
                    "notes": "",
                }
            )
    return len(prompts)


def main() -> int:
    parser = argparse.ArgumentParser(description="对比 base 和 candidate 两份 eval JSONL，生成 CSV 人工评估表。")
    parser.add_argument("--base", required=True, help="基线模型 eval results JSONL。")
    parser.add_argument("--candidate", required=True, help="候选模型 eval results JSONL。")
    parser.add_argument("--output", default="eval/compare_results.csv", help="输出 CSV 路径。")
    args = parser.parse_args()
    count = compare(Path(args.base), Path(args.candidate), Path(args.output))
    print(f"对比完成：对齐 {count} 条 prompt，输出：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
