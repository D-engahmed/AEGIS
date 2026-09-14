"""Evaluator mappers: plugin specs to wire schemas."""

from __future__ import annotations

from ..schemas import EvaluatorSpecOut


def evaluator_spec_out(spec, *, requires_trace: bool) -> EvaluatorSpecOut:
    return EvaluatorSpecOut(
        identity=spec.identity,
        version=spec.version,
        display_name=spec.display_name,
        metrics=list(spec.metrics),
        requires_trace=requires_trace,
        severity=spec.severity,
        unit=spec.unit,
    )


__all__ = ["evaluator_spec_out"]
