"""Redis-backed job queue implementing the at-least-once Queue port (layer 02).

FIFO delivery, matching the in-memory adapter's semantics: `put` appends to the
pending list, `claim` atomically moves a job from the head of pending to the
tail of processing (`LMOVE LEFT->RIGHT`), `complete` drops it, and `abandon`
puts it back at the head so a failed claim is redelivered rather than lost
(at-least-once, worker.py).
"""

from __future__ import annotations

import redis


class RedisQueue:
    def __init__(self, url: str) -> None:
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._key = "aegis:queue:pending"
        self._processing = "aegis:queue:processing"

    def put(self, job_id: str) -> None:
        self._client.rpush(self._key, job_id)

    def claim(self) -> str | None:
        value = self._client.lmove(self._key, self._processing, "LEFT", "RIGHT")
        return str(value) if value is not None else None

    def complete(self, job_id: str) -> None:
        self._client.lrem(self._processing, 0, job_id)

    def abandon(self, job_id: str) -> None:
        self._client.lrem(self._processing, 0, job_id)
        self._client.lpush(self._key, job_id)

    def pending(self) -> int:
        return self._client.llen(self._key)

    def processing_count(self) -> int:
        return self._client.llen(self._processing)

    def clear(self) -> None:
        self._client.delete(self._key, self._processing)


__all__ = ["RedisQueue"]
