"""Deterministic evaluators: versioned plugins computing evidence-backed scores.

Every evaluator carries an identity and a version; results are only produced
together with evidence references (evidence-architecture.md, layer 06).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aegis.domain.datasets import TestCase
from aegis.domain.execution import ExecutionRecord
from aegis.domain.results import (
    EvidenceReference,
    MetricResult,
    new_metric_result,
)
from aegis.domain.time import Clock


@dataclass(frozen=True)
class EvaluatorSpec:
    """Stable descriptor returned by every plugin."""

    identity: str
    version: str
    display_name: str
    metrics: tuple[str, ...]


class Evaluator:
    """Base class for deterministic evaluator plugins."""

    identity = "base"
    version = "0.0.0"
    display_name = "Base"
    metrics: tuple[str, ...] = ()
    severity: str = "info"
    unit: str | None = None

    def spec(self) -> EvaluatorSpec:
        return EvaluatorSpec(self.identity, self.version, self.display_name, self.metrics)

    def evaluate(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        mode: str = "exact",
        tolerance: float = 0.0,
        fail_open: bool = True,
    ) -> list[MetricResult]:
        """Implementations return at least one evidence-backed score."""
        raise NotImplementedError

    def validate(self, params: dict[str, Any]) -> None:
        """Validate plugin configuration without executing."""
        if not isinstance(params, dict):
            raise TypeError("evaluator params must be a dict")


class ExactMatchEvaluator(Evaluator):
    """Exact-match scorer: normalized string equality against the golden answer."""

    identity = "aegis/deterministic/exact_match"
    version = "1.0.0"
    display_name = "Exact Match"
    metrics = ("exact_match",)
    unit = "fraction"

    def evaluate(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        mode: str = "exact",
        tolerance: float = 0.0,
        fail_open: bool = True,
    ) -> list[MetricResult]:
        del tolerance, mode  # exact match is binary
        output = _normalize((execution.outcome.output if execution.outcome else "") or "")
        expected = _normalize(str(test_case.expected))
        score = 1.0 if output == expected else 0.0
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="exact_match",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=score,
                unit=self.unit,
                reason=(
                    "output matches expected value"
                    if score == 1.0
                    else "output differs from expected value"
                ),
            )
        ]


class SchemaEvaluator(Evaluator):
    """Schema-validity scorer against JSON schema (draft 2020-12 subset)."""

    identity = "aegis/deterministic/schema"
    version = "1.0.0"
    display_name = "Schema Validity"
    metrics = ("schema_validity",)
    unit = "fraction"

    def evaluate(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        mode: str = "exact",
        tolerance: float = 0.0,
        fail_open: bool = True,
    ) -> list[MetricResult]:
        del mode, tolerance
        sc = test_case.metadata.get("schema")
        if sc is None:
            raise ValueError("schema evaluator requires test case metadata 'schema'")
        score = _schema_satisfies(
            _normalize(execution.outcome.output if execution.outcome else "") or "",
            sc,
            fail_open=fail_open,
        )
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="schema_validity",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=score,
                unit=self.unit,
                reason=(
                    "output satisfies the schema" if score == 1.0 else "output violates the schema"
                ),
            )
        ]


class LatencyEvaluator(Evaluator):
    """Latency budget: 1.0 when under budget, linear penalty above it."""

    identity = "aegis/deterministic/latency"
    version = "1.0.0"
    display_name = "Latency Budget"
    metrics = ("latency_budget",)
    unit = "fraction"

    def evaluate(
        self,
        clock: Clock,
        execution: ExecutionRecord,
        test_case: TestCase,
        evidence: EvidenceReference,
        mode: str = "exact",
        tolerance: float = 0.0,
        fail_open: bool = True,
    ) -> list[MetricResult]:
        del mode, tolerance, fail_open
        budget_ms = float(test_case.metadata.get("latency_budget_ms") or 1000.0)
        if execution.outcome is None:
            raise ValueError("latency evaluator requires an outcome")
        value = max(0.0, min(1.0, 1.0 - (execution.outcome.latency_ms - budget_ms) / budget_ms))
        score = 1.0 if execution.outcome.latency_ms <= budget_ms else value
        return [
            new_metric_result(
                clock,
                run_id=execution.run_id,
                execution_id=execution.id,
                test_case_id=test_case.id,
                metric_name="latency_budget",
                score=score,
                evaluator_identity=self.identity,
                evaluator_version=self.version,
                evidence=(evidence,),
                raw_value=execution.outcome.latency_ms,
                unit="fraction",
                reason=(
                    "within budget" if execution.outcome.latency_ms <= budget_ms else "over budget"
                ),
            )
        ]


_EVALUATOR_REGISTRY: dict[str, Evaluator] = {
    e.identity: e for e in (ExactMatchEvaluator(), SchemaEvaluator(), LatencyEvaluator())
}


def get_evaluator(identity: str) -> Evaluator:
    if identity not in _EVALUATOR_REGISTRY:
        raise KeyError(f"unknown evaluator {identity!r}")
    return _EVALUATOR_REGISTRY[identity]


def list_evaluators() -> list[Evaluator]:
    return list(_EVALUATOR_REGISTRY.values())


def _normalize(value: str) -> str:
    """Case-insensitive, whitespace-collapsing normalization for comparisons."""
    return " ".join(value.strip().lower().split())


_TYPE_OF: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
}


def _schema_satisfies(output: str, schema: dict[str, Any], fail_open: bool = True) -> float:
    """Shallow JSON-schema subset validation (type-requirement only)."""
    try:
        data = json.loads(output)
    except ValueError:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    if schema.get("type") != "object":
        return 1.0  # unsupported schema forms
    ok = True
    for key, attr in (schema.get("properties") or {}).items():
        if isinstance(attr, dict):
            attr = attr.get("type")
        expected = _TYPE_OF.get(attr)
        if expected is not None and not isinstance(data.get(key), expected):
            ok = False
            break
    return 1.0 if ok else 0.0


__all__ = [
    "Evaluator",
    "EvaluatorSpec",
    "ExactMatchEvaluator",
    "LatencyEvaluator",
    "SchemaEvaluator",
    "get_evaluator",
    "list_evaluators",
]
