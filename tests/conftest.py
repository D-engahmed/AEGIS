"""Shared fakes and fixtures for AEGIS unit tests."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pytest import fixture

from aegis.application.evaluation import EvaluationService
from aegis.application.ports import TargetInvocation, TargetInvocationError
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.execution import ExperimentSnapshot, run_created
from aegis.domain.failures import FailureCode
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.domain.time import Clock, FrozenClock
from aegis.execution.engine import ExecutionEngine
from aegis.execution.retry import RetryPolicy
from aegis.execution.timeout import TimeoutPolicy
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryExecutionRepository,
    MemoryResultRepository,
    MemoryRunRepository,
)


class SteppingClock(FrozenClock):
    """Deterministic clock that advances by a fixed step on every now() call."""

    def __init__(self, step: timedelta, at: datetime | None = None) -> None:
        super().__init__(at)
        self._step = step
        self.random = random.Random(1)

    def now(self) -> datetime:
        value = self._at
        self._at = value + self._step
        return value


@dataclass
class ScriptedCall:
    request: object
    timeout_seconds: float


class ScriptedTarget:
    """Deterministic fake target; steps are consumed in order (last repeats)."""

    def __init__(self, *steps) -> None:
        self._steps = list(steps)
        self.calls: list[ScriptedCall] = []

    def invoke(self, request, timeout_seconds: float) -> TargetInvocation:
        self.calls.append(ScriptedCall(request, timeout_seconds))
        step = self._steps[min(len(self.calls) - 1, len(self._steps) - 1)] if self._steps else "ok"
        if isinstance(step, FailureCode):
            raise TargetInvocationError(step, f"scripted {step.value}")
        if isinstance(step, str):
            return TargetInvocation(
                output=step,
                latency_ms=1.0,
                trace_artifact_id=f"trace/{request.test_case_id}",
            )
        if isinstance(step, TargetInvocation):
            return step
        raise TypeError(f"invalid scripted step: {step!r}")


@fixture
def make_target_version(clock: Clock):
    def _make(*, clock: Clock | None = None, label: str = "1.0.0") -> object:
        at = clock or _clock
        target = create_target(at, "org:1", "prj:1", "fake-target", TargetType.LLM_APPLICATION)
        return create_target_version(
            at, target, label, config={"model": "fake"}, commit_sha="abc123"
        )

    _clock = clock
    return _make


@fixture
def make_dataset_version(clock: Clock):
    def _make(*cases: tuple[object, object] | object, clock: Clock | None = None):
        at = clock or _clock
        dataset = create_dataset(at, "org:1", "prj:1", "golden-qa")
        version, _ = create_dataset_version(at, dataset, "1.0.0")
        for case in cases:
            if isinstance(case, tuple):
                version, _ = add_test_case(at, version, input=case[0], expected=case[1])
            else:
                version, _ = add_test_case(at, version, input=case)
        if version.test_case_count:
            version = lock_dataset_version(at, version)[0]
        return version

    _clock = clock
    return _make


@fixture
def make_run(clock: Clock):
    def _make(
        experiment_id: str = "exp:1",
        target_version_id: str = "tvr:1",
        dataset_version_id: str = "dsv:1",
        *,
        created_by: str = "alice",
        idempotency_key: str | None = None,
        clock: Clock | None = None,
    ):
        at = clock or _clock
        snapshot = ExperimentSnapshot(
            target_version_id=target_version_id,
            dataset_version_id=dataset_version_id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        )
        return run_created(
            at,
            "org:1",
            "prj:1",
            experiment_id,
            snapshot,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )

    _clock = clock
    return _make


@fixture
def make_harness(clock: Clock):
    def _make(
        *,
        run,
        target_version,
        dataset_version,
        target: ScriptedTarget | None = None,
        retry: RetryPolicy | None = None,
        timeouts: TimeoutPolicy | None = None,
        sleep=None,
        clock: Clock | None = None,
    ):
        at = clock or _clock
        target = target or ScriptedTarget()
        runs = MemoryRunRepository()
        runs.save(run)
        executions = MemoryExecutionRepository()
        results = MemoryResultRepository()
        catalog = InMemoryDataCatalog()
        catalog.register_target(target_version)
        catalog.register_dataset(dataset_version)
        registry = InMemoryCancellationRegistry()
        gateway = EvaluationService(at)
        engine = ExecutionEngine(
            client=target,
            gateway=gateway,
            runs=runs,
            executions=executions,
            results=results,
            catalog=catalog,
            cancellations=registry,
            clock=at,
            retry=retry or RetryPolicy(),
            timeouts=timeouts or TimeoutPolicy(),
            sleep=sleep or (lambda _seconds: None),
        )
        return SimpleNamespace(
            engine=engine,
            runs=runs,
            executions=executions,
            results=results,
            registry=registry,
            target=target,
        )

    _clock = clock
    return _make


@fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC))


__all__ = ["ScriptedTarget", "SteppingClock"]
