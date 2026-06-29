from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class QueueMessage:
    message_id: str
    queue_name: str
    payload: dict[str, Any]
    region: str = "default"
    attempts: int = 0
    available_at: float = 0.0
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_message(queue_name: str, payload: dict[str, Any], *, region: str = "default", delay_seconds: int = 0) -> QueueMessage:
    now = time.time()
    return QueueMessage(message_id=f"msg_{uuid.uuid4().hex}", queue_name=queue_name, payload=payload, region=region, attempts=0, available_at=now + delay_seconds, created_at=now)


class QueueStore:
    def enqueue(self, queue_name: str, payload: dict[str, Any], *, region: str = "default", delay_seconds: int = 0) -> QueueMessage:
        raise NotImplementedError

    def claim(self, queue_name: str, *, region: str | None = None, now: float | None = None) -> QueueMessage | None:
        raise NotImplementedError

    def ack(self, message_id: str) -> bool:
        raise NotImplementedError

    def retry(self, message_id: str, *, delay_seconds: int = 0) -> bool:
        raise NotImplementedError

    def dead_letter(self, message_id: str, *, reason: str) -> bool:
        raise NotImplementedError

    def stats(self) -> dict[str, Any]:
        raise NotImplementedError
