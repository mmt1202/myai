"""Create a reproducible training run manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def count_jsonl(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def build_manifest(project_root: Path, config_path: Path, run_name: str) -> dict[str, object]:
    config = read_simple_yaml(config_path)
    dataset_dir = project_root / config.get("dataset_dir", "datasets")
    train_file = dataset_dir / "train.jsonl"
    val_file = dataset_dir / "val.jsonl"
    output_dir = config.get("output_dir", f"saves/{run_name}")
    return {
        "run_name": run_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path.relative_to(project_root)),
        "config_sha256": sha256_file(config_path),
        "model_name_or_path": config.get("model_name_or_path"),
        "dataset": config.get("dataset"),
        "eval_dataset": config.get("eval_dataset"),
        "train_file": str(train_file.relative_to(project_root)),
        "train_rows": count_jsonl(train_file),
        "train_sha256": sha256_file(train_file),
        "val_file": str(val_file.relative_to(project_root)),
        "val_rows": count_jsonl(val_file),
        "val_sha256": sha256_file(val_file),
        "output_dir": output_dir,
        "commands": {
            "validate_train": "python scripts/validate_dataset.py --file datasets/train.jsonl",
            "validate_val": "python scripts/validate_dataset.py --file datasets/val.jsonl",
            "train_linux_macos": f"bash scripts/train_lora.sh {config_path.relative_to(project_root)}",
            "train_windows": f".\\scripts\\train_lora.ps1 -Config {config_path.relative_to(project_root)}",
            "merge_linux_macos": f"bash scripts/merge_lora.sh {config.get('model_name_or_path')} {output_dir} models/{run_name}-merged",
            "merge_windows": f".\\scripts\\merge_lora.ps1 -BaseModel {config.get('model_name_or_path')} -AdapterPath {output_dir} -OutputPath models/{run_name}-merged",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a P0 text LoRA training run manifest.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default="configs/qwen2_5_1_5b_lora.yaml")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    config_path = (project_root / args.config).resolve()
    run_name = args.run_name or config_path.stem
    manifest = build_manifest(project_root, config_path, run_name)
    output_path = project_root / (args.output or f"outputs/training_runs/{run_name}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"training run manifest written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
