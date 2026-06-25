"""Register a trained model version."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_version_entry(
    project_root: Path,
    version: str,
    manifest_path: Path,
    adapter_path: str | None,
    merged_model_path: str | None,
    eval_result_path: str | None,
    notes: str,
) -> dict[str, Any]:
    manifest = load_json(manifest_path, {})
    eval_path = project_root / eval_result_path if eval_result_path else None
    return {
        "version": version,
        "status": "registered",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "base_model": manifest.get("model_name_or_path"),
        "training_manifest": str(manifest_path.relative_to(project_root)),
        "training_manifest_sha256": sha256_file(manifest_path),
        "config_path": manifest.get("config_path"),
        "config_sha256": manifest.get("config_sha256"),
        "train_file": manifest.get("train_file"),
        "train_sha256": manifest.get("train_sha256"),
        "val_file": manifest.get("val_file"),
        "val_sha256": manifest.get("val_sha256"),
        "adapter_path": adapter_path,
        "merged_model_path": merged_model_path,
        "eval_result_path": eval_result_path,
        "eval_result_sha256": sha256_file(eval_path) if eval_path else None,
        "notes": notes,
    }


def upsert_version(registry: dict[str, Any], entry: dict[str, Any], activate: bool) -> dict[str, Any]:
    versions = [item for item in registry.get("versions", []) if item.get("version") != entry["version"]]
    versions.append(entry)
    versions.sort(key=lambda item: item.get("version", ""))
    registry["versions"] = versions
    if activate:
        registry["active_version"] = entry["version"]
    registry.setdefault("active_version", None)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a trained model version.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--registry", default="configs/model_versions.json")
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--adapter-path", default=None)
    parser.add_argument("--merged-model-path", default=None)
    parser.add_argument("--eval-result", default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    registry_path = project_root / args.registry
    manifest_path = (project_root / args.manifest).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"training manifest not found: {manifest_path}")

    registry = load_json(registry_path, {"active_version": None, "versions": []})
    entry = build_version_entry(
        project_root=project_root,
        version=args.version,
        manifest_path=manifest_path,
        adapter_path=args.adapter_path,
        merged_model_path=args.merged_model_path,
        eval_result_path=args.eval_result,
        notes=args.notes,
    )
    registry = upsert_version(registry, entry, args.activate)
    save_json(registry_path, registry)
    print(f"registered model version: {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
