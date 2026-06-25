from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/model_versions.json")
    parser.add_argument("--status", default=None)
    args = parser.parse_args()
    path = Path(args.registry)
    data = json.loads(path.read_text(encoding="utf-8"))
    versions = data.get("versions", [])
    if args.status:
        versions = [item for item in versions if item.get("status") == args.status]
    print(json.dumps({"active_version": data.get("active_version"), "versions": versions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
