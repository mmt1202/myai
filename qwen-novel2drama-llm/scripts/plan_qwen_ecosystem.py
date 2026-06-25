"""输出 Qwen 生态在 AI 短剧工厂中的阶段规划。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_matrix(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_by_stage(matrix: dict[str, Any], stage: str | None) -> list[dict[str, str]]:
    families = matrix.get("families", [])
    if stage is None:
        return families
    return [item for item in families if item.get("stage") == stage]


def main() -> int:
    parser = argparse.ArgumentParser(description="查看 Qwen 生态扩展到 AI 短剧全链路的阶段规划。")
    parser.add_argument("--matrix", default="datasets/model_family_matrix.json", help="模型家族规划 JSON。")
    parser.add_argument("--stage", default=None, help="可选阶段过滤，例如 P0/P1/P2/P3/Aux。")
    args = parser.parse_args()
    matrix = load_matrix(Path(args.matrix))
    rows = filter_by_stage(matrix, args.stage)
    print(json.dumps({"product_positioning": matrix.get("product_positioning"), "families": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
