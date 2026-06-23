"""从 JSONL 数据集中随机抽样。"""
from __future__ import annotations

import argparse
import random
from pathlib import Path


def sample_lines(input_path: Path, output_path: Path, size: int, seed: int) -> int:
    """随机抽样非空 JSONL 行。"""
    lines = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(seed)
    rng.shuffle(lines)
    selected = lines[: min(size, len(lines))]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(selected) + ("\n" if selected else ""), encoding="utf-8")
    return len(selected)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 JSONL 数据集中随机抽样，便于人工质检。")
    parser.add_argument("--input", required=True, help="输入 JSONL 文件。")
    parser.add_argument("--output", required=True, help="输出抽样 JSONL 文件。")
    parser.add_argument("--size", type=int, default=20, help="抽样数量，默认 20。")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，默认 42。")
    args = parser.parse_args()
    if args.size <= 0:
        raise ValueError("--size 必须大于 0。")
    count = sample_lines(Path(args.input), Path(args.output), args.size, args.seed)
    print(f"抽样完成：{count} 条，输出：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
