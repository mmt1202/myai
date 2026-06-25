from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOP_WORDS = {
    "the", "and", "for", "with", "from", "into", "this", "that", "add", "update", "change", "fix", "make",
    "一个", "增加", "新增", "修改", "修复", "实现", "功能", "接口", "文件", "脚本", "测试",
}


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    return [token for token in raw if len(token) > 1 and token not in STOP_WORDS]


def score_text(text: str, tokens: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(token) for token in tokens)


def rank_files(context_index: dict[str, Any], task: str, limit: int) -> list[dict[str, Any]]:
    tokens = tokenize(task)
    ranked: list[dict[str, Any]] = []
    for item in context_index.get("files", []):
        path = str(item.get("path", ""))
        score = score_text(path, tokens)
        if score > 0:
            ranked.append(
                {
                    "path": path,
                    "score": score,
                    "sha256": item.get("sha256"),
                    "chunk_count": item.get("chunk_count"),
                    "reason": "task keyword matched file path",
                }
            )
    ranked.sort(key=lambda item: (-item["score"], item["path"]))
    return ranked[:limit]


def rank_symbols(symbol_index: dict[str, Any], task: str, limit: int) -> list[dict[str, Any]]:
    tokens = tokenize(task)
    ranked: list[dict[str, Any]] = []
    for file_entry in symbol_index.get("files", []):
        path = file_entry.get("path")
        for symbol in file_entry.get("symbols", []):
            name = str(symbol.get("name", ""))
            score = score_text(name, tokens) + score_text(str(path), tokens)
            if score > 0:
                ranked.append({"path": path, "score": score, **symbol})
    ranked.sort(key=lambda item: (-item["score"], item.get("path", ""), item.get("line", 0)))
    return ranked[:limit]


def default_steps(task: str, files: list[dict[str, Any]], symbols: list[dict[str, Any]]) -> list[str]:
    steps = [
        "Rebuild or refresh context indexes before editing.",
        "Read the top ranked files and related chunks.",
    ]
    if symbols:
        steps.append("Inspect the matched symbols and their call sites before modifying code.")
    if files:
        steps.append("Apply the smallest coherent change in the selected target files.")
    else:
        steps.append("Identify target files manually because the current index did not produce strong matches.")
    steps.extend(
        [
            "Add or update tests for the changed behavior.",
            "Run the focused tests first, then run the broader relevant test suite.",
            "Review generated diff before committing.",
        ]
    )
    return steps


def infer_tests(files: list[dict[str, Any]], symbols: list[dict[str, Any]]) -> list[str]:
    tests = {"python -m unittest discover tests"}
    for item in files:
        path = str(item.get("path", ""))
        if path.startswith("tests/") and path.endswith(".py"):
            tests.add(f"python -m unittest {path[:-3].replace('/', '.')}")
    for item in symbols:
        path = str(item.get("path", ""))
        if path.startswith("tests/") and path.endswith(".py"):
            tests.add(f"python -m unittest {path[:-3].replace('/', '.')}")
    return sorted(tests)


def create_patch_plan(task: str, context_index: dict[str, Any], symbol_index: dict[str, Any], file_limit: int = 8, symbol_limit: int = 12) -> dict[str, Any]:
    files = rank_files(context_index, task, file_limit)
    symbols = rank_symbols(symbol_index, task, symbol_limit)
    return {
        "task": task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_files": files,
        "related_symbols": symbols,
        "steps": default_steps(task, files, symbols),
        "tests_to_run": infer_tests(files, symbols),
        "safety_rules": [
            "Do not edit model weights or generated artifacts.",
            "Do not touch files outside the project root.",
            "Prefer small focused patches over broad rewrites.",
            "Keep a reproducible plan before modifying files.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--context-index", default="outputs/context_index.json")
    parser.add_argument("--symbols", default="outputs/code_symbols.json")
    parser.add_argument("--output", default="outputs/patch_plan.json")
    parser.add_argument("--file-limit", type=int, default=8)
    parser.add_argument("--symbol-limit", type=int, default=12)
    args = parser.parse_args()
    context_index = load_json(Path(args.context_index), {"files": []})
    symbol_index = load_json(Path(args.symbols), {"files": []})
    plan = create_patch_plan(args.task, context_index, symbol_index, args.file_limit, args.symbol_limit)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patch plan written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
