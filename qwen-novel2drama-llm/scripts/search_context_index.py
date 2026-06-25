from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_index(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return text.lower()


def line_matches(path: Path, query: str, limit: int) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    query_norm = normalize(query)
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if query_norm in normalize(line):
            matches.append({"line": line_no, "text": line.strip()})
            if len(matches) >= limit:
                break
    return matches


def search_index(project_root: Path, index_path: Path, query: str, per_file_limit: int = 3) -> list[dict[str, Any]]:
    index = load_index(index_path)
    results: list[dict[str, Any]] = []
    query_norm = normalize(query)
    for item in index.get("files", []):
        rel = item.get("path", "")
        path = project_root / rel
        if not path.exists() or not path.is_file():
            continue
        path_match = query_norm in normalize(rel)
        matches = line_matches(path, query, per_file_limit)
        if path_match or matches:
            results.append(
                {
                    "path": rel,
                    "sha256": item.get("sha256"),
                    "chunk_count": item.get("chunk_count"),
                    "path_match": path_match,
                    "matches": matches,
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--index", default="outputs/context_index.json")
    parser.add_argument("--query", required=True)
    parser.add_argument("--per-file-limit", type=int, default=3)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    results = search_index(project_root, project_root / args.index, args.query, args.per_file_limit)[: args.limit]
    print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
