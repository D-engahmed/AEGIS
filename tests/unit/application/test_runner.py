"""EvaluationRunner: in-process end-to-end orchestration over a target client."""

from __future__ import annotations

import pytest

from aegis.application.evaluation import EvaluationService
from aegis.application.runner import EvaluationRunner
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryEvidenceRepository,
    MemoryExecutionRepository,
    MemoryExperimentRepository,
    MemoryQueue,
    MemoryResultRepository,
    MemoryRunRepository,
)
from tests.conftest import ScriptedTarget

pytestmark = pytest.mark.unit


def _build(clock, cases: tuple[tuple[str, str], ...]):
    dataset = create_dataset(clock, "org:1", "prj:1", "cli-qa")
    version, _ = create_dataset_version(clock, dataset, "1.0.0")
    for input, expected in cases:
        version, _ = add_test_case(clock, version, input=input, expected=expected)
    locked, _ = lock_dataset_version(clock, version)

    target = create_target(clock, "org:1", "prj:1", "t", TargetType.MODEL_API)
    target_version = create_target_version(
        clock, target, "1.0.0", config={"base_url": "http://localhost:1234"}
    )

    catalog = InMemoryDataCatalog()
    catalog.register_target(target_version)
    catalog.register_dataset(locked)

    experiment, _ = create_experiment(
        clock,
        "org:1",
        "prj:1",
        "cli-eval",
        snapshot=ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=locked.id,
            evaluator_version_ids=("aegis/deterministic/exact_match",),
            settings={},
        ),
    )

    runner = EvaluationRunner(
        clock,
        experiments=MemoryExperimentRepository(),
        runs=MemoryRunRepository(),
        executions=MemoryExecutionRepository(),
        results=MemoryResultRepository(),
        catalog=catalog,
        cancellations=InMemoryCancellationRegistry(),
        queue=MemoryQueue(),
        evidence=MemoryEvidenceRepository(),
        gateway=EvaluationService(clock),
    )
    return runner, target_version, locked, experiment


def test_runner_executes_success_and_persists_evidence(clock) -> None:
    runner, target_version, dataset_version, experiment = _build(
        clock, (("hello", "hello"), ("world", "world"))
    )
    out = runner.run(
        ScriptedTarget("hello", "world"),
        target_version,
        dataset_version,
        experiment,
    )
    assert out.run.status.value == "succeeded"
    assert {r.score for r in out.results} == {1.0}
    assert len(out.results) == 2
    assert len(out.evidence) == 2


__all__ = []
