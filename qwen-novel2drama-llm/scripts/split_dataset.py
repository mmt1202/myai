"""按比例拆分 JSONL 数据集为训练集和验证集。"""
from __future__ import annotations

import argparse
import random
from pathlib import Path


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在：{path}")
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="将 JSONL 数据按比例拆分为 train/val。")
    parser.add_argument("--input", required=True, help="输入 JSONL 文件。")
    parser.add_argument("--train", required=True, help="输出训练集 JSONL 路径。")
    parser.add_argument("--val", required=True, help="输出验证集 JSONL 路径。")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="验证集比例，默认 0.1。")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，默认 42。")
    args = parser.parse_args()

    if not 0 < args.val_ratio < 1:
        raise ValueError("--val-ratio 必须在 0 到 1 之间。")

    lines = read_lines(Path(args.input))
    rng = random.Random(args.seed)
    rng.shuffle(lines)
    val_size = max(1, int(len(lines) * args.val_ratio)) if len(lines) > 1 else len(lines)
    val_lines = lines[:val_size]
    train_lines = lines[val_size:]
    write_lines(Path(args.train), train_lines)
    write_lines(Path(args.val), val_lines)
    print(f"拆分完成：train={len(train_lines)}，val={len(val_lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
