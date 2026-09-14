"""Wire parity: every response schema has a matching SDK model with the same fields.

A field added, removed, or renamed on one side without the other breaks
typed clients silently (the SDK parser tolerates missing/extra keys by
design). These tests fail loudly on any drift.

Schemas deliberately without an SDK model live in KNOWN_GAPS; adding SDK
coverage for one must move it into SCHEMA_MODEL_PAIRS here.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

import aegis.interface.schemas as schemas
import aegis_sdk.models as sdk_models
from aegis_sdk.models import ApiModel

pytestmark = pytest.mark.contract

SCHEMA_MODEL_PAIRS: tuple[tuple[type, type], ...] = (
    (schemas.CatalogTargetOut, sdk_models.CatalogTarget),
    (schemas.CatalogDatasetOut, sdk_models.CatalogDataset),
    (schemas.CatalogOut, sdk_models.CatalogSummary),
    (schemas.ExperimentSnapshotOut, sdk_models.ExperimentSnapshot),
    (schemas.ExperimentOut, sdk_models.Experiment),
    (schemas.RunOut, sdk_models.Run),
    (schemas.MetricResultOut, sdk_models.MetricResult),
    (schemas.EvaluatorSpecOut, sdk_models.EvaluatorSpec),
    (schemas.GateDecisionOut, sdk_models.GateDecision),
    (schemas.RunVerdictOut, sdk_models.GateReport),
    (schemas.TrendPointOut, sdk_models.TrendPoint),
    (schemas.TrendReportOut, sdk_models.TrendReport),
    (schemas.HealthCheckOut, sdk_models.HealthCheck),
    (schemas.HealthSummaryOut, sdk_models.HealthSummary),
    (schemas.TokenOut, sdk_models.Token),
)

KNOWN_GAPS: frozenset[str] = frozenset(
    {
        # Evidence endpoints have schemas but no SDK surface yet.
        "EvidenceRecordOut",
        "ProvenanceOut",
        # Defined but unused (no endpoint returns it).
        "ArtifactRefOut",
        # PII redaction returns an untyped dict through the SDK.
        "PiiRedactOut",
    }
)


@pytest.mark.parametrize("schema_cls,model_cls", SCHEMA_MODEL_PAIRS, ids=lambda c: c.__name__)
def test_schema_and_sdk_model_share_field_names(schema_cls, model_cls) -> None:
    """Response schema fields and SDK model fields must match exactly."""
    schema_fields = set(schema_cls.model_fields)
    model_fields = {f.name for f in dataclasses.fields(model_cls)}
    assert schema_fields == model_fields, (
        f"{schema_cls.__name__} vs {model_cls.__name__}: "
        f"schema-only={sorted(schema_fields - model_fields)}, "
        f"sdk-only={sorted(model_fields - schema_fields)}"
    )


def test_every_response_schema_is_paired_or_a_known_gap() -> None:
    """Closed world: no *Out schema may drift without a parity entry."""
    out_schemas = {
        name for name, obj in vars(schemas).items() if name.endswith("Out") and inspect.isclass(obj)
    }
    paired = {schema_cls.__name__ for schema_cls, _ in SCHEMA_MODEL_PAIRS}
    assert out_schemas - paired - KNOWN_GAPS == set(), (
        f"unpaired response schemas: {sorted(out_schemas - paired - KNOWN_GAPS)}"
    )
    assert paired & KNOWN_GAPS == set(), "a schema cannot be both paired and a gap"


def test_sdk_models_all_derive_from_api_model() -> None:
    """Every SDK model must inherit the tolerant parse() contract."""
    for _, model_cls in SCHEMA_MODEL_PAIRS:
        assert issubclass(model_cls, ApiModel), model_cls.__name__
