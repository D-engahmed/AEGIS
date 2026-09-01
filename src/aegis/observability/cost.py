"""Cost tracking: target cost vs. evaluator cost, separated per run."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .models import MetricDefinitions


class CostTracker(Protocol):
    """Records and reports AI spend per run, target separated from evaluator."""

    def record_target_cost(self, run_id: str, cost_usd: float) -> None: ...
    def record_evaluator_cost(self, run_id: str, cost_usd: float) -> None: ...
    def total_cost(self, run_id: str) -> float: ...
    def target_cost(self, run_id: str) -> float: ...
    def evaluator_cost(self, run_id: str) -> float: ...


class InMemoryCostTracker:
    """Simple per-run ledger; pushes a metric event to an optional sink."""

    def __init__(self, on_metric: Callable[[str, str, float], None] | None = None) -> None:
        self._target: dict[str, float] = {}
        self._evaluator: dict[str, float] = {}
        self._on_metric = on_metric

    def record_target_cost(self, run_id: str, cost_usd: float) -> None:
        self._target[run_id] = self._target.get(run_id, 0.0) + cost_usd
        if self._on_metric is not None:
            self._on_metric(run_id, MetricDefinitions.TARGET_COST_USD, cost_usd)

    def record_evaluator_cost(self, run_id: str, cost_usd: float) -> None:
        self._evaluator[run_id] = self._evaluator.get(run_id, 0.0) + cost_usd
        if self._on_metric is not None:
            self._on_metric(run_id, MetricDefinitions.EVALUATOR_COST_USD, cost_usd)

    def total_cost(self, run_id: str) -> float:
        return self.target_cost(run_id) + self.evaluator_cost(run_id)

    def target_cost(self, run_id: str) -> float:
        return self._target.get(run_id, 0.0)

    def evaluator_cost(self, run_id: str) -> float:
        return self._evaluator.get(run_id, 0.0)


__all__ = ["CostTracker", "InMemoryCostTracker"]
