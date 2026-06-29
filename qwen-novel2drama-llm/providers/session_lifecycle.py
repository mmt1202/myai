from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderSessionState:
    session_id: str
    provider: str
    protocol: str
    status: str
    opened_at: str | None = None
    closed_at: str | None = None
    last_event_at: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metadata"] = self.metadata or {}
        return data


VALID_SESSION_STATUSES = {"opening", "open", "degraded", "closing", "closed", "failed"}
TERMINAL_SESSION_STATUSES = {"closed", "failed"}
VALID_SESSION_TRANSITIONS = {
    "opening": {"open", "failed", "closed"},
    "open": {"degraded", "closing", "closed", "failed"},
    "degraded": {"open", "closing", "closed", "failed"},
    "closing": {"closed", "failed"},
    "closed": set(),
    "failed": set(),
}


class ProviderSessionLifecycleError(RuntimeError):
    pass


def validate_session_status(status: str) -> str:
    if status not in VALID_SESSION_STATUSES:
        raise ProviderSessionLifecycleError(f"invalid provider session status: {status}")
    return status


def can_transition_session(current_status: str, next_status: str) -> bool:
    validate_session_status(current_status)
    validate_session_status(next_status)
    return next_status in VALID_SESSION_TRANSITIONS[current_status]


def transition_session(state: ProviderSessionState, next_status: str, *, at: str | None = None, metadata: dict[str, Any] | None = None) -> ProviderSessionState:
    if not can_transition_session(state.status, next_status):
        raise ProviderSessionLifecycleError(f"invalid provider session transition: {state.status} -> {next_status}")
    merged_metadata = {**(state.metadata or {}), **(metadata or {})}
    return ProviderSessionState(
        session_id=state.session_id,
        provider=state.provider,
        protocol=state.protocol,
        status=next_status,
        opened_at=state.opened_at or (at if next_status == "open" else None),
        closed_at=at if next_status in TERMINAL_SESSION_STATUSES else state.closed_at,
        last_event_at=at or state.last_event_at,
        metadata=merged_metadata,
    )


def session_health(state: ProviderSessionState) -> dict[str, Any]:
    if state.status == "open":
        status = "ok"
    elif state.status == "degraded":
        status = "degraded"
    elif state.status in TERMINAL_SESSION_STATUSES:
        status = "closed"
    else:
        status = "starting"
    return {"status": status, "session": state.to_dict(), "terminal": state.status in TERMINAL_SESSION_STATUSES}
