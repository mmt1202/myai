from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent.postgres_migration_history import migration_plan


@dataclass(frozen=True)
class DbOpsPlan:
    operation: str
    status: str
    migration_id: str | None = None
    sql_path: str | None = None
    reversible: bool = False
    requires_backup: bool = True
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rollback_plan(*, migration_id: str, reason: str | None = None) -> dict[str, Any]:
    notes = [
        "automatic rollback is not executed by the foundation runtime",
        "operator must restore from a verified backup or run a reviewed down migration",
        "schema_migrations history should be inspected before rollback",
    ]
    if reason:
        notes.append(f"reason: {reason}")
    return DbOpsPlan(operation="rollback", status="manual_review_required", migration_id=migration_id, reversible=False, requires_backup=True, notes=tuple(notes)).to_dict()


def forward_migration_plan(sql_path: Path | str, *, migration_id: str | None = None) -> dict[str, Any]:
    plan = migration_plan(sql_path, migration_id=migration_id)
    return {**DbOpsPlan(operation="forward_migration", status="ready_for_apply", migration_id=plan["migration_id"], sql_path=plan["sql_path"], reversible=False, requires_backup=True, notes=("dry-run before apply", "take a backup before production apply", "checksum conflicts must block apply")).to_dict(), "migration": plan}


def db_ops_health(*, migration_history_enabled: bool, backup_configured: bool = False, rollback_runbook_present: bool = True) -> dict[str, Any]:
    missing: list[str] = []
    if not migration_history_enabled:
        missing.append("migration_history")
    if not backup_configured:
        missing.append("verified_backup")
    if not rollback_runbook_present:
        missing.append("rollback_runbook")
    return {"status": "ok" if not missing else "degraded", "missing": missing, "migration_history_enabled": migration_history_enabled, "backup_configured": backup_configured, "rollback_runbook_present": rollback_runbook_present}
