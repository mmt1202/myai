from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "Dockerfile",
    "compose.production.yml",
    "configs/deploy/production.example.env",
    "docs/p1_hardening.md",
    "migrations/postgres_run_store.sql",
    "migrations/postgres_quota_store.sql",
]

REQUIRED_FLAGS = [
    "P1_api_middleware_quota_checks_implemented_v1 = true",
    "P1_production_deployment_profile_implemented_v1 = true",
    "P1_health_readiness_checks_implemented_v1 = true",
    "P1_pool_health_checks_implemented_v1 = true",
    "P1_queue_observability_implemented_v1 = true",
    "P1_provider_session_lifecycle_hardening_implemented_v1 = true",
    "P1_db_ops_rollback_planning_implemented_v1 = true",
    "P1_billing_global_limit_hardening_implemented_v1 = true",
]


def load_env_template(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def preflight(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    files = {path: (project_root / path).exists() for path in REQUIRED_FILES}
    missing_files = [path for path, exists in files.items() if not exists]
    status_doc = project_root / "docs" / "implementation_status.md"
    status_text = status_doc.read_text(encoding="utf-8") if status_doc.exists() else ""
    missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in status_text]
    env_values = load_env_template(project_root / "configs" / "deploy" / "production.example.env")
    unsafe_env_values = [key for key, value in env_values.items() if value and "<configured outside git>" not in value and key.endswith(("DSN", "KEY", "TOKEN", "SECRET"))]
    return {
        "status": "ok" if not missing_files and not missing_flags and not unsafe_env_values else "failed",
        "files": files,
        "missing_files": missing_files,
        "missing_flags": missing_flags,
        "unsafe_env_values": unsafe_env_values,
        "env_keys": sorted(env_values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check production hardening artifacts without reading real secrets.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()
    report = preflight(Path(args.project_root))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
