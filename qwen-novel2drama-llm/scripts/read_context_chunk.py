from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_chunk(project_root: Path, file_path: str, chunk_id: int, chunk_chars: int) -> dict[str, Any]:
    path = (project_root / file_path).resolve()
    if not path.is_relative_to(project_root):
        raise ValueError(f"file is outside project root: {file_path}")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"file not found: {file_path}")
    text = path.read_text(encoding="utf-8")
    start = chunk_id * chunk_chars
    end = start + chunk_chars
    if chunk_id < 0 or start >= len(text):
        raise ValueError(f"chunk out of range: {chunk_id}")
    chunk = text[start:end]
    return {
        "path": file_path,
        "chunk_id": chunk_id,
        "chunk_chars": chunk_chars,
        "start_char": start,
        "end_char": min(end, len(text)),
        "total_chars": len(text),
        "text": chunk,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--profile", default="configs/context_profile.json")
    parser.add_argument("--path", required=True)
    parser.add_argument("--chunk", type=int, default=0)
    parser.add_argument("--chunk-chars", type=int, default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    profile = load_profile(project_root / args.profile)
    chunk_chars = args.chunk_chars or int(profile.get("chunk_chars", 4000))
    result = read_chunk(project_root, args.path, args.chunk, chunk_chars)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
