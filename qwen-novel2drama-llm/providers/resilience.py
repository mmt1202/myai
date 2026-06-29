from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


RETRYABLE_ERROR_CODES = {"timeout", "rate_limit_exceeded", "provider_unavailable", "provider_error", "network_error"}


@dataclass(frozen=True)
class ProviderHealth:
    model_id: str
    provider: str
    status: str = "unknown"
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None
    cost_score: float = 1.0

    def score(self) -> float:
        total = self.success_count + self.failure_count
        success_rate = 1.0 if total == 0 else self.success_count / total
        failure_penalty = min(0.5, self.consecutive_failures * 0.1)
        latency_penalty = min(0.3, (self.latency_ms_p95 or 0) / 10000.0)
        cost_penalty = min(0.2, max(0.0, self.cost_score - 1.0) * 0.05)
        status_bonus = 0.1 if self.status in {"ok", "configured"} else 0.0
        return max(0.0, min(1.0, success_rate + status_bonus - failure_penalty - latency_penalty - cost_penalty))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["score"] = self.score()
        return data


@dataclass(frozen=True)
class CircuitBreakerState:
    model_id: str
    status: str = "closed"
    failure_count: int = 0
    failure_threshold: int = 3
    recovery_after_seconds: int = 60
    opened_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_retryable_error(error: dict[str, Any] | Exception) -> bool:
    if isinstance(error, Exception):
        retryable = getattr(error, "retryable", None)
        code = getattr(error, "code", None)
        return bool(retryable) or str(code) in RETRYABLE_ERROR_CODES
    return bool(error.get("retryable")) or str(error.get("code")) in RETRYABLE_ERROR_CODES


def next_retry_delay_seconds(attempt: int, *, base_delay: float = 0.5, max_delay: float = 30.0) -> float:
    return min(max_delay, base_delay * (2 ** max(0, attempt - 1)))


def record_circuit_success(state: CircuitBreakerState) -> CircuitBreakerState:
    return CircuitBreakerState(model_id=state.model_id, status="closed", failure_count=0, failure_threshold=state.failure_threshold, recovery_after_seconds=state.recovery_after_seconds, opened_at=None)


def record_circuit_failure(state: CircuitBreakerState, *, now: float | None = None) -> CircuitBreakerState:
    failure_count = state.failure_count + 1
    if failure_count >= state.failure_threshold:
        return CircuitBreakerState(model_id=state.model_id, status="open", failure_count=failure_count, failure_threshold=state.failure_threshold, recovery_after_seconds=state.recovery_after_seconds, opened_at=now)
    return CircuitBreakerState(model_id=state.model_id, status=state.status, failure_count=failure_count, failure_threshold=state.failure_threshold, recovery_after_seconds=state.recovery_after_seconds, opened_at=state.opened_at)


def circuit_allows_request(state: CircuitBreakerState, *, now: float | None = None) -> bool:
    if state.status == "closed":
        return True
    if state.status == "half_open":
        return True
    if state.opened_at is None or now is None:
        return False
    return (now - state.opened_at) >= state.recovery_after_seconds


def rank_fallback_candidates(candidates: list[dict[str, Any]], health: dict[str, ProviderHealth] | None = None, *, required_capabilities: list[str] | None = None) -> list[dict[str, Any]]:
    required = set(required_capabilities or [])
    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        caps = set(candidate.get("capabilities") or [])
        if required and not required.issubset(caps):
            continue
        model_id = str(candidate.get("id") or candidate.get("model_id") or "")
        h = (health or {}).get(model_id)
        score = h.score() if h else 0.5
        if candidate.get("status") == "configured":
            score += 0.1
        scored.append((score, candidate))
    return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]


def fallback_plan(candidates: list[dict[str, Any]], *, primary_model_id: str | None = None, health: dict[str, ProviderHealth] | None = None, required_capabilities: list[str] | None = None) -> dict[str, Any]:
    ranked = rank_fallback_candidates(candidates, health, required_capabilities=required_capabilities)
    ordered = [item for item in ranked if item.get("id") != primary_model_id]
    if primary_model_id:
        primary = [item for item in ranked if item.get("id") == primary_model_id]
        ordered = primary + ordered
    return {"primary_model_id": primary_model_id or (ordered[0].get("id") if ordered else None), "candidates": ordered, "candidate_count": len(ordered)}
