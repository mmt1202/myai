from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionProfile:
    region: str
    healthy: bool = True
    backlog: int = 0
    cost_weight: float = 1.0
    latency_ms: int = 100


def choose_region(regions: list[RegionProfile], *, preferred_region: str | None = None) -> dict[str, Any]:
    healthy = [item for item in regions if item.healthy]
    if preferred_region:
        for item in healthy:
            if item.region == preferred_region:
                return {"status": "selected", "region": item.region, "reason": "preferred_healthy"}
    if not healthy:
        return {"status": "failed", "region": None, "reason": "no_healthy_region"}
    selected = sorted(healthy, key=lambda item: (item.backlog, item.cost_weight, item.latency_ms, item.region))[0]
    return {"status": "selected", "region": selected.region, "reason": "lowest_backlog_cost_latency"}
