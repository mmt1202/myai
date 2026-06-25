from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def iter_python_files(project_root: Path, paths: list[str] | None = None) -> list[Path]:
    if paths:
        files = [project_root / path for path in paths if path.endswith(".py")]
    else:
        files = list(project_root.rglob("*.py"))
    excluded = {".git", ".venv", "__pycache__", ".cache", "models", "saves", "outputs", "logs"}
    return sorted(path for path in files if path.is_file() and not any(part in excluded for part in path.relative_to(project_root).parts))


def read_context_paths(index_path: Path) -> list[str] | None:
    if not index_path.exists():
        return None
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return [item["path"] for item in data.get("files", []) if str(item.get("path", "")).endswith(".py")]


def import_name(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        return ", ".join(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = "." * node.level + (node.module or "")
        names = ", ".join(alias.name for alias in node.names)
        return f"{module}: {names}"
    return ""


def collect_symbols(path: Path, project_root: Path) -> dict[str, Any]:
    rel = path.relative_to(project_root).as_posix()
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=rel)
    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(
                {
                    "name": node.name,
                    "type": "class" if isinstance(node, ast.ClassDef) else "function",
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                }
            )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append({"line": node.lineno, "name": import_name(node)})
    symbols.sort(key=lambda item: (item["line"], item["name"]))
    imports.sort(key=lambda item: item["line"])
    return {"path": rel, "symbols": symbols, "imports": imports}


def build_symbol_index(project_root: Path, context_index: Path | None = None) -> dict[str, Any]:
    paths = read_context_paths(context_index) if context_index else None
    files = iter_python_files(project_root, paths)
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in files:
        try:
            entries.append(collect_symbols(path, project_root))
        except SyntaxError as exc:
            errors.append({"path": path.relative_to(project_root).as_posix(), "error": str(exc)})
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": project_root.name,
        "file_count": len(entries),
        "files": entries,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--context-index", default="outputs/context_index.json")
    parser.add_argument("--output", default="outputs/code_symbols.json")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    context_index = project_root / args.context_index
    index = build_symbol_index(project_root, context_index if context_index.exists() else None)
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"code symbol index written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
