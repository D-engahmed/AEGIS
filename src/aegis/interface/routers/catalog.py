"""Catalog endpoints: register and list target/dataset versions.

These back the dashboard's "register a target / create a dataset" workflow so
an experiment can pin real catalog versions. Registration is a single domain
step (target + version / dataset + draft version + test cases) and every write
is audited.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from aegis.domain.datasets import add_test_case, create_dataset, create_dataset_version
from aegis.domain.targets import TargetType, create_target, create_target_version
from aegis.security.models import Permission

from ..container import Container
from ..deps import Actor, audit, get_container, require_permission
from ..schemas import (
    CatalogDatasetOut,
    CatalogOut,
    CatalogTargetOut,
    DatasetRegisterIn,
    TargetRegisterIn,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _target_out(container: Container, version) -> CatalogTargetOut:
    record = container.catalog.get_target(version.target_id)
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


def _dataset_out(container: Container, version) -> CatalogDatasetOut:
    record = container.catalog.get_dataset(version.dataset_id)
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


@router.get("", response_model=CatalogOut)
def list_catalog(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> CatalogOut:
    """List registered target and dataset versions within the tenant."""
    actor.organization.require_membership(actor.context.user_id)
    org = actor.context.organization_id
    targets = [_target_out(container, v) for v in container.catalog.list_target_versions(org)]
    datasets = [_dataset_out(container, v) for v in container.catalog.list_dataset_versions(org)]
    return CatalogOut(targets=targets, datasets=datasets)


@router.get("/targets", response_model=list[CatalogTargetOut])
def list_targets(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[CatalogTargetOut]:
    """List registered target versions within the tenant."""
    actor.organization.require_membership(actor.context.user_id)
    org = actor.context.organization_id
    return [_target_out(container, v) for v in container.catalog.list_target_versions(org)]


@router.get("/datasets", response_model=list[CatalogDatasetOut])
def list_datasets(
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> list[CatalogDatasetOut]:
    """List registered dataset versions within the tenant."""
    actor.organization.require_membership(actor.context.user_id)
    org = actor.context.organization_id
    return [_dataset_out(container, v) for v in container.catalog.list_dataset_versions(org)]


@router.get("/targets/{target_version_id}", response_model=CatalogTargetOut)
def get_target(
    target_version_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> CatalogTargetOut:
    """Fetch a single target version."""
    actor.organization.require_membership(actor.context.user_id)
    org = actor.context.organization_id
    version = container.catalog.load_target_version(target_version_id)
    if version.organization_id != org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _target_out(container, version)


@router.get("/datasets/{dataset_version_id}", response_model=CatalogDatasetOut)
def get_dataset(
    dataset_version_id: str,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_VIEW))],
    container: Annotated[Container, Depends(get_container)],
) -> CatalogDatasetOut:
    """Fetch a single dataset version."""
    actor.organization.require_membership(actor.context.user_id)
    org = actor.context.organization_id
    version = container.catalog.load_dataset_version(dataset_version_id)
    if version.organization_id != org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _dataset_out(container, version)


@router.post("/targets", response_model=CatalogTargetOut, status_code=201)
def register_target(
    payload: TargetRegisterIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_CREATE))],
    container: Annotated[Container, Depends(get_container)],
) -> CatalogTargetOut:
    """Register a target application and its first immutable config version."""
    org = actor.context.organization_id
    actor.organization.require_membership(actor.context.user_id)
    target = create_target(
        container.clock,
        org,
        payload.project_id,
        payload.name,
        TargetType(payload.target_type),
    )
    version = create_target_version(
        container.clock,
        target,
        payload.label,
        payload.config,
        commit_sha=payload.commit_sha,
    )
    container.catalog.register_target_record(target)
    container.catalog.register_target(version)
    audit(container, actor, "target.registered", "target", target.id)
    return _target_out(container, version)


@router.post("/datasets", response_model=CatalogDatasetOut, status_code=201)
def register_dataset(
    payload: DatasetRegisterIn,
    actor: Annotated[Actor, Depends(require_permission(Permission.EXPERIMENT_CREATE))],
    container: Annotated[Container, Depends(get_container)],
) -> CatalogDatasetOut:
    """Register a dataset and a draft version with its initial test cases."""
    org = actor.context.organization_id
    actor.organization.require_membership(actor.context.user_id)
    dataset = create_dataset(container.clock, org, payload.project_id, payload.name)
    version, _event = create_dataset_version(container.clock, dataset, payload.label)
    for test_case in payload.test_cases:
        version, _event = add_test_case(
            container.clock,
            version,
            input=test_case.input,
            expected=test_case.expected,
            metadata=test_case.metadata,
        )
    container.catalog.register_dataset_record(dataset)
    container.catalog.register_dataset(version)
    audit(container, actor, "dataset.registered", "dataset", dataset.id)
    return _dataset_out(container, version)


__all__ = ["router"]
