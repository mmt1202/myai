from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from runtime_registry import load_runtime_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/model_registry.json")
    parser.add_argument("--capability", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args()
    registry = load_runtime_registry(args.registry)
    rows = registry.list_runtimes(capability=args.capability, status=args.status)
    print(json.dumps({"default_runtime": registry.default_runtime, "runtimes": [row.to_public_dict() for row in rows]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
