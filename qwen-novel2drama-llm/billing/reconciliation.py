from __future__ import annotations

from collections import defaultdict
from typing import Any

from billing.usage_records import ProviderUsageRecord


def summarize_provider_records(records: list[ProviderUsageRecord]) -> dict[str, Any]:
    by_workspace: dict[str, dict[str, Any]] = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "cost": 0.0, "records": 0})
    for record in records:
        row = by_workspace[record.workspace_id]
        row["input_tokens"] += record.input_tokens
        row["output_tokens"] += record.output_tokens
        row["cost"] += record.cost
        row["records"] += 1
    return {"workspace_count": len(by_workspace), "workspaces": {key: {**value, "cost": round(value["cost"], 6)} for key, value in by_workspace.items()}}


def reconcile_usage(local_usage: dict[str, Any], records: list[ProviderUsageRecord], *, tolerance: float = 0.01) -> dict[str, Any]:
    provider_summary = summarize_provider_records(records)
    local_by_workspace = local_usage.get("workspaces") or {}
    issues = []
    for workspace_id, provider_row in provider_summary["workspaces"].items():
        local_row = local_by_workspace.get(workspace_id, {})
        local_cost = float(local_row.get("cost") or 0.0)
        provider_cost = float(provider_row.get("cost") or 0.0)
        delta = round(provider_cost - local_cost, 6)
        if abs(delta) > tolerance:
            issues.append({"workspace_id": workspace_id, "type": "cost_mismatch", "local_cost": local_cost, "provider_cost": provider_cost, "delta": delta})
    return {"status": "matched" if not issues else "mismatch", "provider_summary": provider_summary, "issue_count": len(issues), "issues": issues}
