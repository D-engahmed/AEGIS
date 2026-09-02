"""Evaluation runner: end-to-end orchestration for an in-process evaluation.

Wires the execution engine over a real target client and a registered snapshot,
drives the worker synchronously, and returns the run, its metric results, and the
persisted evidence records. It is the application-facing entry point both the CLI
(layer 03) and the end-to-end test use, so the in-process evaluation path is
exercised exactly once.

No HTTP framework and no queue internals live here; the runner composes the
execution layer and the application services already owned by the container.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from aegis.application.ports import (
    CancellationRegistry,
    DataCatalog,
    EvaluationGateway,
    ExecutionRepository,
    ExperimentRepository,
    Queue,
    ResultRepository,
    RunRepository,
    TargetClient,
)
from aegis.domain import (
    DatasetVersion,
    Experiment,
    ExperimentSnapshot,
    MetricResult,
    Run,
    TargetVersion,
)
from aegis.domain.execution import run_created
from aegis.domain.time import Clock
from aegis.evidence.build import link_evidence_to_score
from aegis.evidence.models import EvidenceRecord
from aegis.evidence.ports import EvidenceRepository
from aegis.execution.engine import ExecutionEngine
from aegis.execution.retry import RetryPolicy
from aegis.execution.timeout import TimeoutPolicy
from aegis.execution.worker import ExecutionWorker
from aegis.policy.ports import RunGateStore


@dataclass(frozen=True)
class EvaluationOutcome:
    """The coordinated result of a completed in-process evaluation."""

    run: Run
    results: tuple[MetricResult, ...]
    evidence: tuple[EvidenceRecord, ...]


class EvaluationRunner:
    """Run a deterministic evaluation end-to-end against a registered snapshot."""

    def __init__(
        self,
        clock: Clock,
        *,
        experiments: ExperimentRepository,
        runs: RunRepository,
        executions: ExecutionRepository,
        results: ResultRepository,
        catalog: DataCatalog,
        cancellations: CancellationRegistry,
        queue: Queue,
        evidence: EvidenceRepository,
        gateway: EvaluationGateway,
        retry: RetryPolicy | None = None,
        timeouts: TimeoutPolicy | None = None,
        run_gate_store: RunGateStore | None = None,
        sleep=None,
    ) -> None:
        self._clock = clock
        self._experiments = experiments
        self._runs = runs
        self._executions = executions
        self._results = results
        self._catalog = catalog
        self._cancellations = cancellations
        self._queue = queue
        self._evidence = evidence
        self._gateway = gateway
        self._retry = retry or RetryPolicy()
        self._timeouts = timeouts or TimeoutPolicy()
        self._run_gate_store = run_gate_store
        self._sleep = sleep or (lambda _seconds: None)

    def engine(self, client: TargetClient, run_gates=None) -> ExecutionEngine:
        """Build the execution engine over a concrete target client."""
        return ExecutionEngine(
            client=client,
            gateway=self._gateway,
            runs=self._runs,
            executions=self._executions,
            results=self._results,
            catalog=self._catalog,
            cancellations=self._cancellations,
            clock=self._clock,
            retry=self._retry,
            timeouts=self._timeouts,
            sleep=self._sleep,
            run_gates=run_gates,
        )

    def run(
        self,
        client: TargetClient,
        target_version: TargetVersion,
        dataset_version: DatasetVersion,
        experiment: Experiment,
        *,
        evaluator_version_ids: Iterable[str] = ("aegis/deterministic/exact_match",),
        created_by: str = "aegis",
        run_gates=None,
    ) -> EvaluationOutcome:
        """Execute one run against `client` and link every result to evidence."""
        snapshot = ExperimentSnapshot(
            target_version_id=target_version.id,
            dataset_version_id=dataset_version.id,
            evaluator_version_ids=tuple(evaluator_version_ids),
            policy_version_id=experiment.snapshot.policy_version_id,
            settings=experiment.snapshot.settings,
        )
        run = run_created(
            self._clock,
            experiment.organization_id,
            experiment.project_id,
            experiment.id,
            snapshot,
            created_by=created_by,
        )
        self._experiments.save(experiment)
        self._runs.save(run)
        self._queue.put(run.id)

        engine = self.engine(client, run_gates=run_gates)
        worker = ExecutionWorker(engine, self._queue)
        worker.process_next()

        run = self._runs.load(run.id)
        executions = {ex.id: ex for ex in self._executions.list_for_run(run.id)}
        results = tuple(self._results.list_for_run(run.id))
        evidence_records = []
        for result in results:
            execution = executions.get(result.execution_id)
            if execution is None:
                continue
            record = link_evidence_to_score(
                self._evidence,
                self._clock,
                result,
                execution,
                experiment,
                target_version,
                dataset_version,
            )
            evidence_records.append(record)
        return EvaluationOutcome(run=run, results=results, evidence=tuple(evidence_records))


__all__ = ["EvaluationOutcome", "EvaluationRunner"]
