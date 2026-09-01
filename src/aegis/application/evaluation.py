"""Evaluation scoring gateway: builds evidence references and runs evaluators.

The gateway belongs to the application layer; evaluator plugins live in the
evaluation layer. This composition keeps evaluation decoupled from the worker
(each may be versioned and replaced independently).
"""

from __future__ import annotations

from collections.abc import Iterable

from aegis.application.ports import EvaluationGateway
from aegis.domain import ExecutionRecord, MetricResult, TargetVersion
from aegis.domain.datasets import TestCase
from aegis.domain.results import EvidenceReference
from aegis.domain.time import Clock
from aegis.evaluation.plugins import get_evaluator


class EvaluationService(EvaluationGateway):
    """Implements the scoring boundary: production of evidence-backed metrics."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

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


__all__ = ["EvaluationService"]
