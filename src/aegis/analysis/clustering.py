"""Failure clustering: groups failed executions by root-cause category."""

from __future__ import annotations

from aegis.domain import FailureCode, MetricResult
from aegis.domain.identifiers import new_id

from .models import FailureCategory, FailureClusterReport
from .ports import FailureClassifier

_CATEGORY_BY_CODE: dict[FailureCode, FailureCategory] = {
    FailureCode.AGENT_LOOP: FailureCategory.TOOL,
    FailureCode.TEST_TIMEOUT: FailureCategory.TIMEOUT,
    FailureCode.TARGET_TIMEOUT: FailureCategory.TIMEOUT,
    FailureCode.EXPERIMENT_TIMEOUT: FailureCategory.TIMEOUT,
    FailureCode.NETWORK_TIMEOUT: FailureCategory.TIMEOUT,
    FailureCode.SCHEMA_MISMATCH: FailureCategory.VALIDATION,
    FailureCode.MALFORMED_RESPONSE: FailureCategory.VALIDATION,
    FailureCode.INVALID_CONFIG: FailureCategory.VALIDATION,
    FailureCode.PROVIDER_RATE_LIMIT: FailureCategory.MODEL,
    FailureCode.TEMPORARY_UNAVAILABLE: FailureCategory.RETRIEVAL,
    FailureCode.TARGET_CRASH: FailureCategory.MODEL,
}


def _category_for(result: MetricResult) -> FailureCategory:
    code = result.reason  # the failure code is stored on the metric reason, when present
    if code:
        try:
            parsed = FailureCode(code)
        except ValueError:
            return FailureCategory.UNKNOWN
        return _CATEGORY_BY_CODE.get(parsed, FailureCategory.UNKNOWN)
    if result.severity == "critical":
        return FailureCategory.TOOL
    return FailureCategory.UNKNOWN


class CategoryFailureClassifier(FailureClassifier):
    """Clusters failed results into root-cause categories by failure code."""

    def classify(self, failure_results: list[MetricResult]) -> list[FailureClusterReport]:
        buckets: dict[FailureCategory, list[MetricResult]] = {}
        for result in failure_results:
            buckets.setdefault(_category_for(result), []).append(result)

        reports: list[FailureClusterReport] = []
        for category in sorted(buckets, key=lambda c: c.value):
            members = buckets[category]
            report = FailureClusterReport(
                cluster_id=new_id("clu"),
                failure_category=category,
                count=len(members),
                failure_ids=tuple(m.execution_id for m in members),
                representative_message=members[0].reason or category.value,
                severity=(
                    "high"
                    if category in (FailureCategory.TOOL, FailureCategory.VALIDATION)
                    else "medium"
                ),
            )
            reports.append(report)
        return reports


__all__ = ["CategoryFailureClassifier"]
