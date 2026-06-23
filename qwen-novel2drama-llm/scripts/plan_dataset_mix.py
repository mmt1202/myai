"""根据任务配比规划不同规模的数据集目标数量。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_mix(path: Path) -> list[dict[str, Any]]:
    """读取任务配比 JSON。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    if not tasks:
        raise ValueError("task mix 文件缺少 tasks")
    ratio_sum = sum(float(task.get("ratio", 0)) for task in tasks)
    if abs(ratio_sum - 1.0) > 0.001:
        raise ValueError(f"任务比例之和必须为 1，当前为 {ratio_sum}")
    return tasks


def plan_counts(tasks: list[dict[str, Any]], total: int) -> list[dict[str, Any]]:
    """按比例计算目标数量，并把舍入误差补到最大任务上。"""
    if total <= 0:
        raise ValueError("total 必须大于 0")
    rows: list[dict[str, Any]] = []
    allocated = 0
    for task in tasks:
        count = int(round(total * float(task["ratio"])))
        allocated += count
        rows.append({**task, "target_count": count})
    diff = total - allocated
    if diff != 0:
        largest = max(range(len(rows)), key=lambda index: float(rows[index]["ratio"]))
        rows[largest]["target_count"] += diff
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="根据任务配比生成数据集建设目标。")
    parser.add_argument("--mix", default="datasets/task_mix.json", help="任务配比 JSON。")
    parser.add_argument("--total", type=int, default=500, help="目标样本总数。")
    parser.add_argument("--output", default=None, help="可选：输出 JSON 报告路径。")
    args = parser.parse_args()
    rows = plan_counts(load_mix(Path(args.mix)), args.total)
    report = {"total": args.total, "tasks": rows}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
