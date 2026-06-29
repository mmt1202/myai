from __future__ import annotations

from typing import Any

ALLOWED_TRANSITIONS = {
    "created": {"reviewing", "rejected"},
    "reviewing": {"approved", "redo", "rejected"},
    "redo": {"reviewing", "rejected"},
    "approved": set(),
    "rejected": set(),
}


def transition_status(current: str, target: str) -> dict[str, Any]:
    allowed = target in ALLOWED_TRANSITIONS.get(current, set())
    return {"allowed": allowed, "from": current, "to": target, "reason": "ok" if allowed else "transition_not_allowed"}


def review_asset(asset: dict[str, Any], decision: str, *, reviewer: str = "human") -> dict[str, Any]:
    current = str(asset.get("status") or "created")
    transition = transition_status(current, decision)
    if not transition["allowed"]:
        return {"status": "failed", "transition": transition, "asset": asset}
    updated = dict(asset)
    updated["status"] = decision
    updated["review"] = {"reviewer": reviewer, "decision": decision}
    return {"status": "ok", "transition": transition, "asset": updated}
