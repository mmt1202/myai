from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_PATHS = [
    "deploy/k8s/README.md",
    "deploy/terraform/main.tf",
    "deploy/security/security_profile.yaml",
    "deploy/observability/slo.yaml",
]


def validate_cloud_deploy_profile(project_root: Path) -> dict[str, Any]:
    checks = []
    for relative in REQUIRED_PATHS:
        path = project_root / relative
        checks.append({"path": relative, "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0})
    missing = [item for item in checks if not item["exists"]]
    return {"status": "passed" if not missing else "failed", "checks": checks, "missing": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cloud deployment profile files.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    report = validate_cloud_deploy_profile(Path(args.project_root))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
