from __future__ import annotations

import time
from typing import Any

from external_queue.base import QueueMessage, QueueStore, new_message


class InMemoryExternalQueue(QueueStore):
    def __init__(self) -> None:
        self.pending: list[QueueMessage] = []
        self.inflight: dict[str, QueueMessage] = {}
        self.dead: dict[str, dict[str, Any]] = {}
        self.completed: set[str] = set()

    def enqueue(self, queue_name: str, payload: dict[str, Any], *, region: str = "default", delay_seconds: int = 0) -> QueueMessage:
        message = new_message(queue_name, payload, region=region, delay_seconds=delay_seconds)
        self.pending.append(message)
        return message

    def claim(self, queue_name: str, *, region: str | None = None, now: float | None = None) -> QueueMessage | None:
        current = time.time() if now is None else now
        for index, message in enumerate(self.pending):
            if message.queue_name != queue_name:
                continue
            if region and message.region != region:
                continue
            if message.available_at > current:
                continue
            claimed = QueueMessage(**{**message.to_dict(), "attempts": message.attempts + 1})
            self.pending.pop(index)
            self.inflight[claimed.message_id] = claimed
            return claimed
        return None

    def ack(self, message_id: str) -> bool:
        if message_id not in self.inflight:
            return False
        self.inflight.pop(message_id)
        self.completed.add(message_id)
        return True

    def retry(self, message_id: str, *, delay_seconds: int = 0) -> bool:
        message = self.inflight.pop(message_id, None)
        if not message:
            return False
        self.pending.append(QueueMessage(**{**message.to_dict(), "available_at": time.time() + delay_seconds}))
        return True

    def dead_letter(self, message_id: str, *, reason: str) -> bool:
        message = self.inflight.pop(message_id, None)
        if not message:
            return False
        self.dead[message_id] = {"message": message.to_dict(), "reason": reason, "dead_lettered_at": time.time()}
        return True

    def stats(self) -> dict[str, Any]:
        return {"type": "memory", "pending": len(self.pending), "inflight": len(self.inflight), "dead_letter": len(self.dead), "completed": len(self.completed)}
