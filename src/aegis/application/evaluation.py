"""Evaluation scoring gateway: builds evidence references and runs evaluators.

The gateway belongs to the application layer; evaluator plugins live in the
evaluation layer. This composition keeps evaluation decoupled from the worker
(each may be versioned and replaced independently).

Trajectory evaluators (trajectory.py) read preserved traces and are run by
``evaluate_trajectory`` after the run's spans are flushed; the per-execution
``evaluate`` path only ever runs output-facing evaluators.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from aegis.application.ports import EvaluationGateway
from aegis.domain import ExecutionRecord, MetricResult, Run, TargetVersion
from aegis.domain.datasets import TestCase
from aegis.domain.results import EvidenceReference
from aegis.domain.time import Clock
from aegis.evaluation.plugins import get_evaluator
from aegis.evaluation.trajectory import get_trajectory_evaluator, is_trajectory_identity
from aegis.observability.models import SpanAttributes, TraceRecord

TraceSource = Callable[[str], list[TraceRecord]]


class EvaluationService(EvaluationGateway):
    """Implements the scoring boundary: production of evidence-backed metrics."""

    def __init__(
        self,
        clock: Clock,
        trace_source: TraceSource | None = None,
    ) -> None:
        self._clock = clock
        self._trace_source = trace_source

    def evaluate(
        self,
        execution: ExecutionRecord,
        test_case_id: str,
        target_version: TargetVersion,
        evaluator_version_ids: Iterable[str],
        settings: dict,
    ) -> list[MetricResult]:
        del target_version
        test_case = TestCase(
            id=test_case_id,
            dataset_version_id=execution.dataset_version_id,
            index=execution.sequence,
            input=settings.get("input"),
            expected=settings.get("expected"),
            metadata=settings,
        )
        if execution.outcome is None:
            return []

        evidence = (
            EvidenceReference(
                execution_id=execution.id,
                dataset_case_id=test_case_id,
                trace_artifact_id=execution.outcome.trace_artifact_id,
            ),
        )
        result_evidence = evidence[0]
        results: list[MetricResult] = []
        identities = list(evaluator_version_ids) or ["aegis/deterministic/exact_match"]
        for identity in identities:
            if is_trajectory_identity(identity):
                continue  # handled by evaluate_trajectory once the trace exists
            evaluator = get_evaluator(identity)
            results.extend(
                evaluator.evaluate(
                    self._clock,
                    execution,
                    test_case,
                    result_evidence,
                    mode=settings.get("mode", "exact"),
                    tolerance=float(settings.get("tolerance", 0.0)),
                )
            )
        return results

    def evaluate_trajectory(
        self,
        run: Run,
        executions: Iterable[ExecutionRecord],
        test_cases: Iterable[TestCase],
    ) -> list[MetricResult]:
        """Score preserved traces with every trajectory evaluator configured."""
        if self._trace_source is None:
            return []
        identities = [
            identity
            for identity in run.snapshot.evaluator_version_ids
            if is_trajectory_identity(identity)
        ]
        if not identities:
            return []
        spans_by_execution: dict[str, list[object]] = {}
        for record in self._trace_source(run.id):
            for span in record.spans:
                execution_id = (getattr(span, "attributes", {}) or {}).get(
                    SpanAttributes.EXECUTION_ID
                )
                if execution_id is None:
                    continue
                spans_by_execution.setdefault(str(execution_id), []).append(span)
        test_cases_by_id = {case.id: case for case in test_cases}

        results: list[MetricResult] = []
        for execution in executions:
            test_case = test_cases_by_id[execution.test_case_id]
            if not execution.evidence_references:
                continue
            evidence: EvidenceReference = execution.evidence_references[0]
            spans = spans_by_execution.get(execution.id, [])
            for identity in identities:
                evaluator = get_trajectory_evaluator(identity)
                results.extend(
                    evaluator.evaluate_trajectory(
                        self._clock,
                        execution,
                        test_case,
                        evidence,
                        spans,
                    )
                )
        return results


__all__ = ["EvaluationService"]