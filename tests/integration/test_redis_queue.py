"""Redis-backed queue semantics against the docker-compose redis service."""

from __future__ import annotations

import pytest

from aegis.infrastructure.redis_queue import RedisQueue

pytestmark = pytest.mark.integration


@pytest.fixture
def queue(redis_url: str) -> RedisQueue:
    return RedisQueue(redis_url)


def test_fifo_claim_order(queue: RedisQueue) -> None:
    for job in ("a", "b", "c"):
        queue.put(job)
    assert queue.pending() == 3
    assert queue.claim() == "a"
    assert queue.claim() == "b"


def test_complete_removes_claimed_job(queue: RedisQueue) -> None:
    queue.put("a")
    queue.put("b")
    assert queue.claim() == "a"
    queue.complete("a")
    assert queue.processing_count() == 0
    assert queue.pending() == 1
    assert queue.claim() == "b"


def test_abandon_redelivers_at_head(queue: RedisQueue) -> None:
    for job in ("claim1", "claim2"):
        queue.put(job)
    assert queue.claim() == "claim1"
    queue.abandon("claim1")
    assert queue.processing_count() == 0
    assert queue.claim() == "claim1", "abandoned job is retried before unseen jobs"


def test_claim_empty_returns_none(queue: RedisQueue) -> None:
    assert queue.claim() is None
    assert queue.pending() == 0
    assert queue.processing_count() == 0


def test_clear_resets_both_lists(queue: RedisQueue) -> None:
    queue.put("a")
    queue.claim()
    queue.put("b")
    queue.clear()
    assert queue.pending() == 0
    assert queue.processing_count() == 0
