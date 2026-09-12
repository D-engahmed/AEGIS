"""PostgreSQL adapters for every application/evidence/policy port (layer 02).

Each repository opens a short-lived connection per call, so adapters are
thread-safe and never share cursor state; write-once constraints are enforced
with `ON CONFLICT DO NOTHING` + row-count checks so a duplicate persist raises
`Conflict` exactly like the in-memory adapters. Nested aggregates (snapshots,
evidence provenance, gate reports) round-trip through the jsonb serializers in
`serde.py`; typed columns keep the core fields queryable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg

from aegis.domain import (
    Conflict,
    Dataset,
    DatasetVersion,
    ExecutionRecord,
    Experiment,
    FailureClass,
    FailureCode,
    FailureInfo,
    MetricResult,
    NotFound,
    Run,
    Target,
    TargetVersion,
)
from aegis.domain.execution import (
    EvidenceSummary,
    ExecutionOutcome,
    TokenUsage,
)
from aegis.domain.experiments import ExperimentSnapshot
from aegis.domain.results import EvidenceReference
from aegis.evidence.models import (
    ArtifactReference,
    ArtifactType,
    DataClassification,
    EvidenceRecord,
    ProvenanceSnapshot,
)
from aegis.infrastructure.serde import from_plain, to_plain
from aegis.policy.models import GateDecision, GateOverride, RunGateReport, RunGateVerdict, Verdict


class Psql:
    """Minimal PostgreSQL connection factory; one connection per operation."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connect(self):
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            yield conn


def _snapshot_from(value: Mapping[str, Any]) -> ExperimentSnapshot:
    return ExperimentSnapshot(
        target_version_id=value["target_version_id"],
        dataset_version_id=value["dataset_version_id"],
        evaluator_version_ids=tuple(value["evaluator_version_ids"]),
        policy_version_id=value.get("policy_version_id"),
        settings=dict(value["settings"]),
    )


def _failure_from(value: Mapping[str, Any] | None) -> FailureInfo | None:
    if value is None:
        return None
    return FailureInfo(
        code=FailureCode(value["code"]),
        message=value["message"],
        occurred_at=value["occurred_at"],
        failure_class=FailureClass(value["failure_class"]) if value.get("failure_class") else None,
    )


def _summary_from(value: Mapping[str, Any] | None) -> EvidenceSummary | None:
    if value is None:
        return None
    return EvidenceSummary(
        total_executions=value["total_executions"],
        completed_executions=value["completed_executions"],
        evidence_reference_count=value["evidence_reference_count"],
        partial_preserved=value["partial_preserved"],
    )


def _outcome_from(value: Mapping[str, Any] | None) -> ExecutionOutcome | None:
    if value is None:
        return None
    tokens = value.get("tokens") or {}
    return ExecutionOutcome(
        output=value["output"],
        latency_ms=value["latency_ms"],
        tokens=TokenUsage(
            input_tokens=tokens.get("input_tokens", 0), output_tokens=tokens.get("output_tokens", 0)
        ),
        cost_usd=value["cost_usd"],
        trace_artifact_id=value.get("trace_artifact_id"),
    )


def _evidence_refs_from(value: list | None) -> tuple[EvidenceReference, ...]:
    if not value:
        return ()
    return tuple(
        EvidenceReference(
            execution_id=item["execution_id"],
            dataset_case_id=item["dataset_case_id"],
            trace_artifact_id=item.get("trace_artifact_id"),
            input_fingerprint=item.get("input_fingerprint"),
            expected_fingerprint=item.get("expected_fingerprint"),
        )
        for item in value
    )


def _artifact_from(value: Mapping[str, Any]) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=value["artifact_id"],
        artifact_type=ArtifactType(value["artifact_type"]),
        storage_key=value["storage_key"],
        content_hash=value["content_hash"],
        size_bytes=value["size_bytes"],
        content_type=value["content_type"],
        created_at=value["created_at"],
    )


def _provenance_from(value: Mapping[str, Any]) -> ProvenanceSnapshot:
    return ProvenanceSnapshot(
        experiment_id=value["experiment_id"],
        target_version_id=value["target_version_id"],
        target_config_hash=value["target_config_hash"],
        dataset_version_id=value["dataset_version_id"],
        dataset_hash=value["dataset_hash"],
        evaluator_identities=tuple(value["evaluator_identities"]),
        evaluator_config_hash=value["evaluator_config_hash"],
        policy_version_id=value.get("policy_version_id"),
        snapshot_timestamp=value["snapshot_timestamp"],
    )


def _gate_decision_from(value: Mapping[str, Any]) -> GateDecision:
    return GateDecision(
        value["gate_id"],
        Verdict(value["verdict"]),
        value["reason"],
        aegis_policy_severity(value["severity"]),
    )


def _gate_decision_to(decision: GateDecision) -> dict:
    return {
        "gate_id": decision.gate_id,
        "verdict": decision.verdict.value,
        "reason": decision.reason,
        "severity": decision.severity.value,
    }


def _override_from(value: Mapping[str, Any] | None) -> GateOverride | None:
    if value is None:
        return None
    return GateOverride(
        run_id=value["run_id"],
        overridden_by=value["overridden_by"],
        reason=value["reason"],
        overridden_at=value["overridden_at"],
        gate_ids=tuple(value["gate_ids"]),
    )


def aegis_policy_severity(value: str):
    from aegis.policy.models import GateSeverity

    return GateSeverity(value)


class PostgresExperimentRepository:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def save(self, experiment: Experiment) -> None:
        snapshot = to_plain(experiment.snapshot)
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO experiments
                    (id, organization_id, project_id, name, status, clone_of,
                     created_at, snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """,
                (
                    experiment.id,
                    experiment.organization_id,
                    experiment.project_id,
                    experiment.name,
                    experiment.status.value,
                    experiment.clone_of,
                    experiment.created_at,
                    json_dumps(snapshot),
                ),
            )

    def load(self, experiment_id: str) -> Experiment:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM experiments WHERE id = %s", (experiment_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"experiment {experiment_id!r} not found")
        return _experiment_from(row)

    def exists(self, experiment_id: str) -> bool:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM experiments WHERE id = %s", (experiment_id,))
            return cur.fetchone() is not None

    def list_for_org(self, organization_id: str) -> list[Experiment]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM experiments WHERE organization_id = %s ORDER BY created_at DESC",
                (organization_id,),
            )
            rows = cur.fetchall()
        return [_experiment_from(row) for row in rows]


def _experiment_from(row) -> Experiment:
    return Experiment(
        id=row[0],
        organization_id=row[1],
        project_id=row[2],
        name=row[3],
        status=_experiment_status(row[4]),
        clone_of=row[5],
        created_at=row[6],
        snapshot=_snapshot_from(from_plain(row[7])),
    )


def _experiment_status(value: str):
    from aegis.domain.experiments import ExperimentStatus

    return ExperimentStatus(value)


class PostgresRunRepository:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def save(self, run: Run) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs
                    (id, organization_id, project_id, experiment_id, created_by,
                     created_at, status, started_at, finished_at, snapshot,
                     evidence_summary, executions, error, cancelled_by,
                     cancelled_at, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    evidence_summary = EXCLUDED.evidence_summary,
                    executions = EXCLUDED.executions,
                    error = EXCLUDED.error,
                    cancelled_by = EXCLUDED.cancelled_by,
                    cancelled_at = EXCLUDED.cancelled_at
                """,
                (
                    run.id,
                    run.organization_id,
                    run.project_id,
                    run.experiment_id,
                    run.created_by,
                    run.created_at,
                    run.status.value,
                    run.started_at,
                    run.finished_at,
                    json_dumps(to_plain(run.snapshot)),
                    json_dumps(to_plain(run.evidence_summary)),
                    json_dumps(list(run.executions)),
                    json_dumps(to_plain(run.error)),
                    run.cancelled_by,
                    run.cancelled_at,
                    run.idempotency_key,
                ),
            )

    def load(self, run_id: str) -> Run:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"run {run_id!r} not found")
        return _run_from(row)

    def find_by_idempotency(self, key: str) -> Run | None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE idempotency_key = %s", (key,))
            row = cur.fetchone()
        return _run_from(row) if row is not None else None

    def list_for_org(self, organization_id: str, limit: int = 50) -> list[Run]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM runs WHERE organization_id = %s ORDER BY created_at DESC LIMIT %s",
                (organization_id, limit),
            )
            rows = cur.fetchall()
        return [_run_from(row) for row in rows]

    def list_for_experiment(self, experiment_id: str) -> list[Run]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM runs WHERE experiment_id = %s ORDER BY created_at",
                (experiment_id,),
            )
            rows = cur.fetchall()
        return [_run_from(row) for row in rows]


def _run_from(row) -> Run:
    return Run(
        id=row[0],
        organization_id=row[1],
        project_id=row[2],
        experiment_id=row[3],
        created_by=row[4],
        created_at=row[5],
        status=_run_status(row[6]),
        started_at=row[7],
        finished_at=row[8],
        snapshot=_snapshot_from(from_plain(row[9])),
        evidence_summary=_summary_from(from_plain(row[10])),
        executions=tuple(from_plain(row[11])),
        error=_failure_from(from_plain(row[12])),
        cancelled_by=row[13],
        cancelled_at=row[14],
        idempotency_key=row[15],
    )


def _run_status(value: str):
    from aegis.domain.execution import RunStatus

    return RunStatus(value)


class PostgresExecutionRepository:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def save(self, execution: ExecutionRecord) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO executions
                    (id, run_id, sequence, test_case_id, target_version_id,
                     dataset_version_id, status, created_at, started_at,
                     finished_at, outcome, evidence_references, failure,
                     cancelled_by, retries)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    outcome = EXCLUDED.outcome,
                    evidence_references = EXCLUDED.evidence_references,
                    failure = EXCLUDED.failure,
                    cancelled_by = EXCLUDED.cancelled_by,
                    retries = EXCLUDED.retries
                """,
                (
                    execution.id,
                    execution.run_id,
                    execution.sequence,
                    execution.test_case_id,
                    execution.target_version_id,
                    execution.dataset_version_id,
                    execution.status.value,
                    execution.created_at,
                    execution.started_at,
                    execution.finished_at,
                    json_dumps(to_plain(execution.outcome)),
                    json_dumps(to_plain(execution.evidence_references)),
                    json_dumps(to_plain(execution.failure)),
                    execution.cancelled_by,
                    execution.retries,
                ),
            )

    def load(self, execution_id: str) -> ExecutionRecord:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM executions WHERE id = %s", (execution_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"execution {execution_id!r} not found")
        return _execution_from(row)

    def list_for_run(self, run_id: str) -> list[ExecutionRecord]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM executions WHERE run_id = %s ORDER BY sequence",
                (run_id,),
            )
            return [_execution_from(row) for row in cur.fetchall()]


def _execution_from(row) -> ExecutionRecord:
    return ExecutionRecord(
        id=row[0],
        run_id=row[1],
        sequence=row[2],
        test_case_id=row[3],
        target_version_id=row[4],
        dataset_version_id=row[5],
        status=_execution_status(row[6]),
        created_at=row[7],
        started_at=row[8],
        finished_at=row[9],
        outcome=_outcome_from(from_plain(row[10])),
        evidence_references=_evidence_refs_from(from_plain(row[11])),
        failure=_failure_from(from_plain(row[12])),
        cancelled_by=row[13],
        retries=row[14],
    )


def _execution_status(value: str):
    from aegis.domain.execution import ExecutionStatus

    return ExecutionStatus(value)


class PostgresResultRepository:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def persist(self, results: Iterable[MetricResult]) -> None:
        for result in results:
            with self._db.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO metric_results
                        (id, run_id, execution_id, test_case_id, metric_name,
                         score, evaluator_identity, evaluator_version, created_at,
                         confidence, severity, raw_value, unit, reason,
                         judge_model, judge_prompt_version, evidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        result.id,
                        result.run_id,
                        result.execution_id,
                        result.test_case_id,
                        result.metric_name,
                        result.score,
                        result.evaluator_identity,
                        result.evaluator_version,
                        result.created_at,
                        result.confidence,
                        result.severity,
                        result.raw_value,
                        result.unit,
                        result.reason,
                        result.judge_model,
                        result.judge_prompt_version,
                        json_dumps(to_plain(result.evidence)),
                    ),
                )
                if cur.rowcount == 0:
                    raise Conflict(f"metric result {result.id!r} already persisted")

    def list_for_run(self, run_id: str) -> list[MetricResult]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM metric_results WHERE run_id = %s ORDER BY created_at",
                (run_id,),
            )
            return [_metric_from(row) for row in cur.fetchall()]


def _metric_from(row) -> MetricResult:
    return MetricResult(
        id=row[0],
        run_id=row[1],
        execution_id=row[2],
        test_case_id=row[3],
        metric_name=row[4],
        score=row[5],
        evaluator_identity=row[6],
        evaluator_version=row[7],
        created_at=row[8],
        confidence=row[9],
        severity=row[10],
        raw_value=row[11],
        unit=row[12],
        reason=row[13],
        judge_model=row[14],
        judge_prompt_version=row[15],
        evidence=_evidence_refs_from(from_plain(row[16])),
    )


class PostgresDataCatalog:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def register_target_record(self, target: Target) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO targets
                    (id, organization_id, project_id, name, target_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    target.id,
                    target.organization_id,
                    target.project_id,
                    target.name,
                    target.target_type.value,
                    target.created_at,
                ),
            )

    def register_dataset_record(self, dataset: Dataset) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO datasets
                    (id, organization_id, project_id, name, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    dataset.id,
                    dataset.organization_id,
                    dataset.project_id,
                    dataset.name,
                    dataset.created_at,
                ),
            )

    def get_target(self, target_id: str) -> Target:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM targets WHERE id = %s", (target_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"target {target_id!r} not found")
        from aegis.domain.targets import TargetType

        return Target(
            id=row[0],
            organization_id=row[1],
            project_id=row[2],
            name=row[3],
            target_type=TargetType(row[4]),
            created_at=row[5],
        )

    def get_dataset(self, dataset_id: str) -> Dataset:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"dataset {dataset_id!r} not found")
        return Dataset(
            id=row[0],
            organization_id=row[1],
            project_id=row[2],
            name=row[3],
            created_at=row[4],
        )

    def list_target_versions(self, organization_id: str) -> list[TargetVersion]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM target_versions WHERE organization_id = %s ORDER BY created_at DESC",
                (organization_id,),
            )
            return [_target_version_from(row) for row in cur.fetchall()]

    def list_dataset_versions(self, organization_id: str) -> list[DatasetVersion]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM dataset_versions"
                " WHERE organization_id = %s ORDER BY dataset_id, label",
                (organization_id,),
            )
            versions: list[DatasetVersion] = []
            for row in cur.fetchall():
                with self._db.connect() as conn2, conn2.cursor() as cur2:
                    cur2.execute(
                        "SELECT * FROM test_cases WHERE dataset_version_id = %s ORDER BY seq",
                        (row[0],),
                    )
                    test_rows = cur2.fetchall()
                versions.append(_dataset_version_from(row, test_rows))
            return versions

    def register_target(self, version: TargetVersion) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO target_versions
                    (id, target_id, organization_id, project_id, label, config,
                     created_at, commit_sha, image_digest, referenced)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET referenced = EXCLUDED.referenced
                """,
                (
                    version.id,
                    version.target_id,
                    version.organization_id,
                    version.project_id,
                    str(version.label),
                    json_dumps(dict(version.config)),
                    version.created_at,
                    version.commit_sha,
                    version.image_digest,
                    version.referenced,
                ),
            )

    def register_dataset(self, version: DatasetVersion) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            for test_case in version.test_cases:
                cur.execute(
                    """
                    INSERT INTO test_cases (id, dataset_version_id, seq, input, expected, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        test_case.id,
                        version.id,
                        test_case.index,
                        json_dumps(test_case.input),
                        json_dumps(test_case.expected),
                        json_dumps(dict(test_case.metadata)),
                    ),
                )
            cur.execute(
                """
                INSERT INTO dataset_versions
                    (id, dataset_id, organization_id, project_id, label, status, locked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET status = EXCLUDED.status, locked_at = EXCLUDED.locked_at
                """,
                (
                    version.id,
                    version.dataset_id,
                    version.organization_id,
                    version.project_id,
                    str(version.label),
                    version.status.value,
                    version.locked_at,
                ),
            )

    def load_target_version(self, target_version_id: str) -> TargetVersion:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM target_versions WHERE id = %s", (target_version_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"target version {target_version_id!r} not found")
        return _target_version_from(row)

    def load_dataset_version(self, dataset_version_id: str) -> DatasetVersion:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM dataset_versions WHERE id = %s", (dataset_version_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"dataset version {dataset_version_id!r} not found")
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM test_cases WHERE dataset_version_id = %s ORDER BY seq",
                (dataset_version_id,),
            )
            test_rows = cur.fetchall()
        return _dataset_version_from(row, test_rows)


def _target_version_from(row) -> TargetVersion:
    from aegis.domain.identifiers import VersionLabel

    return TargetVersion(
        id=row[0],
        target_id=row[1],
        organization_id=row[2],
        project_id=row[3],
        label=VersionLabel(row[4]),
        config=dict(from_plain(row[5])),
        created_at=row[6],
        commit_sha=row[7],
        image_digest=row[8],
        referenced=row[9],
    )


def _dataset_version_from(row, test_rows) -> DatasetVersion:
    from aegis.domain.datasets import DatasetStatus, TestCase
    from aegis.domain.identifiers import VersionLabel

    test_cases = tuple(
        TestCase(
            id=r[0],
            dataset_version_id=r[1],
            index=r[2],
            input=from_plain(r[3]),
            expected=from_plain(r[4]),
            metadata=dict(from_plain(r[5])),
        )
        for r in test_rows
    )
    return DatasetVersion(
        id=row[0],
        dataset_id=row[1],
        organization_id=row[2],
        project_id=row[3],
        label=VersionLabel(row[4]),
        status=DatasetStatus(row[5]),
        locked_at=row[6],
        test_cases=test_cases,
    )


class PostgresCancellationRegistry:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def cancel(self, run_id: str, identity: str, clock) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cancellations (run_id, identity, cancelled_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET identity = EXCLUDED.identity
                """,
                (run_id, identity, clock.now()),
            )

    def is_cancelled(self, run_id: str) -> bool:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM cancellations WHERE run_id = %s", (run_id,))
            return cur.fetchone() is not None

    def who_cancelled(self, run_id: str) -> str | None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT identity FROM cancellations WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        return row[0] if row else None


class PostgresEvidenceRepository:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def persist(self, record: EvidenceRecord) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence
                    (id, metric_result_id, run_id, execution_id, experiment_id,
                     evaluator_identity, evaluator_version, dataset_version_id,
                     target_version_id, artifact_references, provenance,
                     classification, created_at, created_by, judge_model,
                     judge_prompt_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    record.id,
                    record.metric_result_id,
                    record.run_id,
                    record.execution_id,
                    record.experiment_id,
                    record.evaluator_identity,
                    record.evaluator_version,
                    record.dataset_version_id,
                    record.target_version_id,
                    json_dumps(to_plain(record.artifact_references)),
                    json_dumps(to_plain(record.provenance)),
                    record.classification.value,
                    record.created_at,
                    record.created_by,
                    record.judge_model,
                    record.judge_prompt_version,
                ),
            )
            if cur.rowcount == 0:
                raise Conflict(f"evidence record {record.id!r} already persisted")

    def get(self, evidence_id: str) -> EvidenceRecord:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM evidence WHERE id = %s", (evidence_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"evidence record {evidence_id!r} not found")
        return _evidence_from(row)

    def list_for_run(self, run_id: str) -> list[EvidenceRecord]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM evidence WHERE run_id = %s ORDER BY created_at", (run_id,))
            return [_evidence_from(row) for row in cur.fetchall()]

    def list_for_metric_result(self, metric_result_id: str) -> list[EvidenceRecord]:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM evidence WHERE metric_result_id = %s ORDER BY created_at",
                (metric_result_id,),
            )
            return [_evidence_from(row) for row in cur.fetchall()]

    def exists(self, evidence_id: str) -> bool:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM evidence WHERE id = %s", (evidence_id,))
            return cur.fetchone() is not None


def _evidence_from(row) -> EvidenceRecord:
    return EvidenceRecord(
        id=row[0],
        metric_result_id=row[1],
        run_id=row[2],
        execution_id=row[3],
        experiment_id=row[4],
        evaluator_identity=row[5],
        evaluator_version=row[6],
        dataset_version_id=row[7],
        target_version_id=row[8],
        artifact_references=tuple(_artifact_from(a) for a in from_plain(row[9])),
        provenance=_provenance_from(from_plain(row[10])),
        classification=DataClassification(row[11]),
        created_at=row[12],
        created_by=row[13],
        judge_model=row[14],
        judge_prompt_version=row[15],
    )


class PostgresProvenanceIndex:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def index(self, record: EvidenceRecord) -> None:
        # The evidence row already carries the provenance snapshot; no-op kept
        # for protocol parity with the in-memory index.
        return

    def provenance_for_result(self, metric_result_id: str) -> ProvenanceSnapshot:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT provenance FROM evidence WHERE metric_result_id = %s",
                (metric_result_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"no provenance indexed for metric result {metric_result_id!r}")
        return _provenance_from(from_plain(row[0]))

    def provenance_for_execution(self, execution_id: str) -> ProvenanceSnapshot:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "SELECT provenance FROM evidence WHERE execution_id = %s "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                (execution_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"no provenance indexed for execution {execution_id!r}")
        return _provenance_from(from_plain(row[0]))


class PostgresArtifactManager:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def store(
        self, artifact_type: ArtifactType, content: bytes, metadata: dict
    ) -> ArtifactReference:
        from aegis.domain.identifiers import new_id

        digest = hashlib.sha256(content).hexdigest()
        reference = ArtifactReference(
            artifact_id=new_id("art"),
            artifact_type=artifact_type,
            storage_key=f"{artifact_type.value}/{digest}",
            content_hash=digest,
            size_bytes=len(content),
            content_type=metadata.get("content_type", "application/octet-stream"),
            created_at=metadata.get("created_at") or datetime.now(UTC),
        )
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence_artifacts
                    (artifact_id, artifact_type, storage_key, content_hash,
                     size_bytes, content_type, created_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (artifact_id) DO NOTHING
                """,
                (
                    reference.artifact_id,
                    reference.artifact_type.value,
                    reference.storage_key,
                    reference.content_hash,
                    reference.size_bytes,
                    reference.content_type,
                    reference.created_at,
                    content,
                ),
            )
        return reference

    def retrieve(self, artifact_id: str) -> bytes:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM evidence_artifacts WHERE artifact_id = %s", (artifact_id,)
            )
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"artifact {artifact_id!r} not found")
        return bytes(row[0])

    def get_reference(self, artifact_id: str) -> ArtifactReference:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM evidence_artifacts WHERE artifact_id = %s", (artifact_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"artifact {artifact_id!r} not found")
        return ArtifactReference(
            artifact_id=row[0],
            artifact_type=ArtifactType(row[1]),
            storage_key=row[2],
            content_hash=row[3],
            size_bytes=row[4],
            content_type=row[5],
            created_at=row[6],
        )

    def delete(self, artifact_id: str) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM evidence_artifacts WHERE artifact_id = %s", (artifact_id,))


class PostgresRunGateStore:
    def __init__(self, db: Psql) -> None:
        self._db = db

    def save(self, report: RunGateReport) -> None:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gate_reports (run_id, verdict, decisions, evaluated_at, override)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    verdict = EXCLUDED.verdict,
                    decisions = EXCLUDED.decisions,
                    evaluated_at = EXCLUDED.evaluated_at,
                    override = EXCLUDED.override
                """,
                (
                    report.run_id,
                    report.verdict.value,
                    json_dumps([_gate_decision_to(d) for d in report.decisions]),
                    report.evaluated_at,
                    json_dumps(_override_to(report.override)),
                ),
            )

    def load(self, run_id: str) -> RunGateReport:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM gate_reports WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
        if row is None:
            raise NotFound(f"gate report for run {run_id!r} not found")
        return RunGateReport(
            run_id=row[0],
            verdict=RunGateVerdict(row[1]),
            decisions=tuple(_gate_decision_from(d) for d in from_plain(row[2])),
            evaluated_at=row[3],
            override=_override_from(from_plain(row[4])),
        )

    def exists(self, run_id: str) -> bool:
        with self._db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM gate_reports WHERE run_id = %s", (run_id,))
            return cur.fetchone() is not None


def _override_to(override: GateOverride | None) -> dict | None:
    if override is None:
        return None
    return {
        "run_id": override.run_id,
        "overridden_by": override.overridden_by,
        "reason": override.reason,
        "overridden_at": to_plain(override.overridden_at),
        "gate_ids": list(override.gate_ids),
    }


def json_dumps(value: Any) -> str | None:
    """Dump pre-encoded plain values; None columns stay None."""
    if value is None:
        return None
    import json

    return json.dumps(value)


class PostgresStore:
    """Bundle of every PostgreSQL adapter over one schema."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.db = Psql(dsn)
        self.experiments = PostgresExperimentRepository(self.db)
        self.runs = PostgresRunRepository(self.db)
        self.executions = PostgresExecutionRepository(self.db)
        self.results = PostgresResultRepository(self.db)
        self.catalog = PostgresDataCatalog(self.db)
        self.cancellations = PostgresCancellationRegistry(self.db)
        self.evidence = PostgresEvidenceRepository(self.db)
        self.provenance = PostgresProvenanceIndex(self.db)
        self.artifacts = PostgresArtifactManager(self.db)
        self.run_gate_store = PostgresRunGateStore(self.db)

    def migrate(self) -> None:
        from aegis.infrastructure.migrations import apply_migrations

        apply_migrations(self.dsn)


__all__ = ["PostgresStore"]
