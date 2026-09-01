"""Execution worker: claims jobs from the queue and runs the engine.

At-least-once semantics: an engine exception causes the job to be abandoned
(redelivered) rather than silently lost; engine.run() is idempotent, so a
redelivered terminal run is a no-op.
"""

from __future__ import annotations

from collections.abc import Callable

from aegis.application.ports import Queue
from aegis.execution.engine import ExecutionEngine


class ExecutionWorker:
    def __init__(self, engine: ExecutionEngine, queue: Queue) -> None:
        self._engine = engine
        self._queue = queue

    def process_next(self) -> bool:
        """Handle one job if present; returns whether any job was claimed."""
        job_id = self._queue.claim()
        if job_id is None:
            return False
        try:
            self._engine.run(job_id)
        except Exception:
            self._queue.abandon(job_id)
            raise
        self._queue.complete(job_id)
        return True

    def pump(self, count: int | None = None, post_step: Callable[[], None] | None = None) -> int:
        """Process jobs until the queue is empty (or `count` jobs are handled)."""
        handled = 0
        while self.process_next():
            handled += 1
            if count is not None and handled >= count:
                break
            if post_step is not None:
                post_step()
        return handled


__all__ = ["ExecutionWorker"]
