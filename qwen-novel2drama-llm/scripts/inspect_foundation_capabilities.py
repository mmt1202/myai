from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="configs/foundation_capability_matrix.json")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--status", default=None)
    args = parser.parse_args()
    data = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    rows = data.get("capabilities", [])
    if args.stage:
        rows = [row for row in rows if row.get("stage") == args.stage]
    if args.status:
        rows = [row for row in rows if row.get("status") == args.status]
    print(
        json.dumps(
            {
                "foundation_positioning": data.get("foundation_positioning"),
                "principle": data.get("principle"),
                "capabilities": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
