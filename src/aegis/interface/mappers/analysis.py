"""Analysis mappers: trend reports to wire schemas."""

from __future__ import annotations

from ..schemas import TrendPointOut, TrendReportOut


def trend_report_out(report) -> TrendReportOut:
    return TrendReportOut(
        metric_name=report.metric_name,
        data_points=[
            TrendPointOut(timestamp=p.timestamp, score=p.score, run_id=p.run_id)
            for p in report.data_points
        ],
        overall_trend=report.overall_trend.value,
        analyzed_at=report.analyzed_at,
    )


__all__ = ["trend_report_out"]
