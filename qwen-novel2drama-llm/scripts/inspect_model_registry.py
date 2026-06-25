"""查看模型运行时注册表。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from runtime_registry import load_runtime_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="查看 Qwen 短剧模型运行时注册表。")
    parser.add_argument("--registry", default="configs/model_registry.json", help="模型运行时注册表路径。")
    parser.add_argument("--capability", default=None, help="按能力过滤，例如 text_generation。")
    parser.add_argument("--status", default=None, help="按状态过滤，例如 implemented/planned。")
    args = parser.parse_args()
    registry = load_runtime_registry(args.registry)
    rows = registry.list_runtimes(capability=args.capability, status=args.status)
    print(
        json.dumps(
            {
                "default_runtime": registry.default_runtime,
                "runtimes": [row.to_public_dict() for row in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
