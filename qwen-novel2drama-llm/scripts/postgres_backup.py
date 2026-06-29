from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BackupPlan:
    operation: str
    status: str
    output_path: str
    dsn_configured: bool
    command: tuple[str, ...]
    executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        return data


def backup_command(*, output_path: Path, dsn_env: str = "FOUNDATION_AGENT_RUN_POSTGRES_DSN") -> tuple[str, ...]:
    return ("pg_dump", "--format=custom", "--file", str(output_path), f"--dbname=${dsn_env}")


def restore_command(*, input_path: Path, dsn_env: str = "FOUNDATION_AGENT_RUN_POSTGRES_DSN") -> tuple[str, ...]:
    return ("pg_restore", "--clean", "--if-exists", f"--dbname=${dsn_env}", str(input_path))


def plan_backup(*, output_path: Path, dsn_env: str = "FOUNDATION_AGENT_RUN_POSTGRES_DSN") -> dict[str, Any]:
    return BackupPlan(operation="backup", status="ready" if os.environ.get(dsn_env) else "missing_dsn", output_path=str(output_path), dsn_configured=bool(os.environ.get(dsn_env)), command=backup_command(output_path=output_path, dsn_env=dsn_env)).to_dict()


def plan_restore(*, input_path: Path, dsn_env: str = "FOUNDATION_AGENT_RUN_POSTGRES_DSN") -> dict[str, Any]:
    status = "ready" if os.environ.get(dsn_env) and input_path.exists() else "not_ready"
    return BackupPlan(operation="restore", status=status, output_path=str(input_path), dsn_configured=bool(os.environ.get(dsn_env)), command=restore_command(input_path=input_path, dsn_env=dsn_env)).to_dict()


def execute_pg_command(command: tuple[str, ...], *, dsn_env: str) -> dict[str, Any]:
    dsn = os.environ.get(dsn_env)
    if not dsn:
        return {"status": "failed", "error": "dsn_missing"}
    argv = [dsn if item == f"${dsn_env}" else item for item in command]
    completed = subprocess.run(argv, check=False, capture_output=True, text=True)
    return {"status": "ok" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "stderr": completed.stderr[-2000:], "stdout": completed.stdout[-2000:]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or execute Postgres backup/restore commands without printing DSN values.")
    parser.add_argument("operation", choices=["backup", "restore"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--dsn-env", default="FOUNDATION_AGENT_RUN_POSTGRES_DSN")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    plan = plan_backup(output_path=path, dsn_env=args.dsn_env) if args.operation == "backup" else plan_restore(input_path=path, dsn_env=args.dsn_env)
    if args.execute:
        command = backup_command(output_path=path, dsn_env=args.dsn_env) if args.operation == "backup" else restore_command(input_path=path, dsn_env=args.dsn_env)
        plan["execution"] = execute_pg_command(command, dsn_env=args.dsn_env)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if plan.get("status") in {"ready", "missing_dsn", "not_ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
