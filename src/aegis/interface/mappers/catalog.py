"""Catalog mappers: versions plus their parent records to wire schemas.

The store lookup stays in the router; these mappers take the already-loaded
(version, record) pair so they remain pure functions of their inputs.
"""

from __future__ import annotations

from ..schemas import CatalogDatasetOut, CatalogTargetOut


def target_out(version, record) -> CatalogTargetOut:
    return CatalogTargetOut(
        id=version.id,
        target_id=version.target_id,
        project_id=version.project_id,
        name=record.name,
        target_type=record.target_type.value,
        label=str(version.label),
        config=dict(version.config),
        created_at=version.created_at,
        referenced=version.referenced,
    )


def dataset_out(version, record) -> CatalogDatasetOut:
    return CatalogDatasetOut(
        id=version.id,
        dataset_id=version.dataset_id,
        project_id=version.project_id,
        name=record.name,
        label=str(version.label),
        status=version.status.value,
        test_case_count=version.test_case_count,
        created_at=record.created_at,
    )


__all__ = ["dataset_out", "target_out"]
