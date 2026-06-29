from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BillingLimitPlan:
    scope: str
    status: str
    quota_backend: str
    global_strong_consistency: bool = False
    external_billing_reconciliation: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def billing_limit_plan(*, quota_backend: str, scope: str = "workspace") -> dict[str, Any]:
    backend = quota_backend.lower().strip()
    distributed = backend in {"postgres", "postgresql", "pg"}
    status = "persistence_ready" if distributed else "local_only"
    notes = [
        "quota backend can support request-time budget checks",
        "external invoice reconciliation is not implemented",
        "global strong consistency requires an external distributed limiter or database-level operational guarantees",
    ]
    if not distributed:
        notes.append("file/sqlite backends are local-node only")
    return BillingLimitPlan(scope=scope, status=status, quota_backend=backend, global_strong_consistency=False, external_billing_reconciliation=False, notes=tuple(notes)).to_dict()


def global_rate_limit_health(*, quota_backend: str, regions: int = 1, external_limiter_configured: bool = False) -> dict[str, Any]:
    backend = quota_backend.lower().strip()
    missing: list[str] = []
    if regions > 1 and not external_limiter_configured:
        missing.append("external_distributed_limiter")
    if backend not in {"postgres", "postgresql", "pg"}:
        missing.append("shared_quota_backend")
    return {"status": "ok" if not missing else "degraded", "quota_backend": backend, "regions": regions, "external_limiter_configured": external_limiter_configured, "missing": missing}


def billing_reconciliation_status(*, invoice_import_configured: bool = False, export_configured: bool = False) -> dict[str, Any]:
    missing = []
    if not invoice_import_configured:
        missing.append("invoice_import")
    if not export_configured:
        missing.append("billing_export")
    return {"status": "ok" if not missing else "planned", "missing": missing, "invoice_import_configured": invoice_import_configured, "export_configured": export_configured}
