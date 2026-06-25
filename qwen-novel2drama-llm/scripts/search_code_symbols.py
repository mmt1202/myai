from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_symbols(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def search_symbols(index_path: Path, query: str, symbol_type: str | None = None) -> list[dict[str, Any]]:
    data = load_symbols(index_path)
    query_norm = query.lower()
    results: list[dict[str, Any]] = []
    for file_entry in data.get("files", []):
        path = file_entry.get("path")
        for symbol in file_entry.get("symbols", []):
            if symbol_type and symbol.get("type") != symbol_type:
                continue
            if query_norm in str(symbol.get("name", "")).lower():
                results.append({"path": path, **symbol})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="outputs/code_symbols.json")
    parser.add_argument("--query", required=True)
    parser.add_argument("--type", default=None, choices=[None, "class", "function"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    results = search_symbols(Path(args.index), args.query, args.type)[: args.limit]
    print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
