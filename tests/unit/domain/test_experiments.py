"""Experiment lifecycle: start, finish guards, and run-status aggregation."""

import pytest

from aegis.domain.exceptions import InvalidState
from aegis.domain.execution import RunStatus
from aegis.domain.experiments import (
    Experiment,
    ExperimentSnapshot,
    ExperimentStatus,
    aggregate_experiment_status,
)

pytestmark = pytest.mark.unit


def test_aggregate_none_when_empty_or_in_flight() -> None:
    assert aggregate_experiment_status([]) is None
    assert aggregate_experiment_status([RunStatus.SUCCEEDED, RunStatus.QUEUED]) is None
    assert aggregate_experiment_status([RunStatus.SUCCEEDED, RunStatus.RUNNING]) is None


def test_aggregate_succeeded_when_all_terminal() -> None:
    assert (
        aggregate_experiment_status([RunStatus.SUCCEEDED, RunStatus.SUCCEEDED])
        is ExperimentStatus.SUCCEEDED
    )


def test_aggregate_failed_wins_over_cancelled_and_succeeded() -> None:
    assert (
        aggregate_experiment_status(
            [RunStatus.SUCCEEDED, RunStatus.CANCELLED, RunStatus.FAILED]
        )
        is ExperimentStatus.FAILED
    )
    assert (
        aggregate_experiment_status([RunStatus.SUCCEEDED, RunStatus.FAILED])
        is ExperimentStatus.FAILED
    )


def test_aggregate_cancelled_when_any_cancelled_and_none_failed() -> None:
    assert (
        aggregate_experiment_status([RunStatus.SUCCEEDED, RunStatus.CANCELLED])
        is ExperimentStatus.CANCELLED
    )


def _experiment(status: ExperimentStatus) -> Experiment:
    return Experiment(
        id="exp:1",
        organization_id="org:1",
        project_id="prj:1",
        name="agg",
        snapshot=ExperimentSnapshot(target_version_id="tvr:1", dataset_version_id="dsv:1"),
        created_at=object(),  # type: ignore[arg-type]
        status=status,
    )


def test_finish_transitions_to_terminal() -> None:
    created = _experiment(ExperimentStatus.CREATED)
    assert created.finish(ExperimentStatus.SUCCEEDED).status is ExperimentStatus.SUCCEEDED
    running = _experiment(ExperimentStatus.RUNNING)
    assert running.finish(ExperimentStatus.CANCELLED).status is ExperimentStatus.CANCELLED


def test_finish_rejects_non_terminal_target_or_double_finish() -> None:
    created = _experiment(ExperimentStatus.CREATED)
    with pytest.raises(InvalidState):
        created.finish(ExperimentStatus.RUNNING)
    done = _experiment(ExperimentStatus.SUCCEEDED)
    with pytest.raises(InvalidState):
        done.finish(ExperimentStatus.FAILED)