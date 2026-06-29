from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEPLOY_REQUIREMENTS = {
    "compose": ["Dockerfile", "compose.production.yml", "configs/deploy/production.example.env"],
    "ci": [".github/workflows/foundation-contract-check.yml", ".github/workflows/foundation-provider-smoke.yml"],
    "docs": ["docs/p1_hardening.md", "docs/implementation_status.md"],
}

CLOUD_SPECIALIZATION_TODO = [
    "Kubernetes / Terraform",
    "AWS/GCP/Azure/Vault secret manager",
    "real certificates, domain, WAF, CDN",
    "Prometheus/Grafana/SLO alerting deployment",
    "real backup policy and RPO/RTO drill",
    "external MQ / cross-region scheduling",
    "real billing invoice import/export",
]


def deploy_profile(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    groups: dict[str, Any] = {}
    missing: list[str] = []
    for group, paths in DEPLOY_REQUIREMENTS.items():
        status = {path: (project_root / path).exists() for path in paths}
        groups[group] = status
        missing.extend([path for path, exists in status.items() if not exists])
    return {"status": "ok" if not missing else "failed", "groups": groups, "missing": missing, "cloud_specialization_todo": CLOUD_SPECIALIZATION_TODO}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository-level deployment profile.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()
    report = deploy_profile(Path(args.project_root))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
