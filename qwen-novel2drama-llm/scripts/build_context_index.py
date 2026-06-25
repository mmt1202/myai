from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_excluded(path: Path, project_root: Path, profile: dict[str, Any]) -> bool:
    rel_parts = path.relative_to(project_root).parts
    excluded_dirs = set(profile.get("exclude_dirs", []))
    if any(part in excluded_dirs for part in rel_parts):
        return True
    return path.suffix.lower() in set(profile.get("exclude_suffixes", []))


def is_included(path: Path, project_root: Path, profile: dict[str, Any]) -> bool:
    rel = path.relative_to(project_root).as_posix()
    return any(fnmatch(rel, pattern) for pattern in profile.get("include_globs", []))


def count_chunks(text: str, chunk_chars: int) -> int:
    if not text:
        return 0
    return (len(text) + chunk_chars - 1) // chunk_chars


def select_files(project_root: Path, profile: dict[str, Any]) -> list[Path]:
    max_file_bytes = int(profile.get("max_file_bytes", 200000))
    files: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path, project_root, profile):
            continue
        if not is_included(path, project_root, profile):
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        files.append(path)
    return sorted(files)


def build_index(project_root: Path, profile_path: Path) -> dict[str, Any]:
    profile = load_profile(profile_path)
    chunk_chars = int(profile.get("chunk_chars", 4000))
    entries: list[dict[str, Any]] = []
    for path in select_files(project_root, profile):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(project_root).as_posix()
        entries.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "line_count": len(text.splitlines()),
                "char_count": len(text),
                "chunk_chars": chunk_chars,
                "chunk_count": count_chunks(text, chunk_chars),
            }
        )
    return {
        "profile": profile.get("profile"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": project_root.name,
        "file_count": len(entries),
        "files": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--profile", default="configs/context_profile.json")
    parser.add_argument("--output", default="outputs/context_index.json")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    index = build_index(project_root, project_root / args.profile)
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"context index written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
