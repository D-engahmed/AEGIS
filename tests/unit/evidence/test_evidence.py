"""Evidence layer (09): provenance records, graph, and adapters."""

from __future__ import annotations

from datetime import datetime

import pytest

from aegis.domain import (
    Conflict,
    DatasetVersion,
    ExecutionOutcome,
    ExecutionRecord,
    ExecutionStatus,
    Experiment,
    ExperimentSnapshot,
    ExperimentStatus,
    MetricResult,
    NotFound,
    TargetVersion,
    TokenUsage,
)
from aegis.domain.datasets import (
    TestCase as AegisTestCase,
)
from aegis.domain.execution import run_created
from aegis.domain.results import EvidenceReference
from aegis.domain.time import FrozenClock
from aegis.evidence.build import build_evidence_record, link_evidence_to_score
from aegis.evidence.graph import InMemoryEvidenceGraph
from aegis.evidence.models import (
    ArtifactReference,
    ArtifactType,
    EdgeType,
    EvidenceEdge,
    EvidenceGraphQuery,
    EvidenceRecord,
    ProvenanceSnapshot,
)
from aegis.evidence.provenance import build_provenance, content_hash
from aegis.infrastructure.memory import (
    MemoryArtifactManager,
    MemoryEvidenceRepository,
    MemoryProvenanceIndex,
)
from aegis.security.models import DataClassification

pytestmark = pytest.mark.unit

_AT = datetime(2026, 8, 30, 12, 0, 0)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(_AT)


@pytest.fixture
def experiment(clock: FrozenClock) -> Experiment:
    return Experiment(
        id="exp:1",
        organization_id="org:1",
        project_id="prj:1",
        name="golden",
        snapshot=ExperimentSnapshot(
            target_version_id="tvr:1",
            dataset_version_id="dsv:1",
            evaluator_version_ids=("aegis/deterministic/exact_match",),
        ),
        created_at=clock.now(),
        status=ExperimentStatus.CREATED,
    )


@pytest.fixture
def target_version() -> TargetVersion:
    return TargetVersion(
        id="tvr:1",
        target_id="tgt:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        config={"model": "fake"},
        commit_sha="deadbeef",
        created_at=_AT,
    )


@pytest.fixture
def dataset_version() -> DatasetVersion:
    return DatasetVersion(
        id="dsv:1",
        dataset_id="ds:1",
        organization_id="org:1",
        project_id="prj:1",
        label="1.0.0",
        test_cases=(
            AegisTestCase(id="tc:1", dataset_version_id="dsv:1", index=0, input="x", expected="y"),
        ),
    )


@pytest.fixture
def execution(clock: FrozenClock) -> ExecutionRecord:
    return ExecutionRecord(
        id="exe:1",
        run_id="run:1",
        sequence=0,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        status=ExecutionStatus.SUCCEEDED,
        created_at=clock.now(),
        started_at=clock.now(),
        finished_at=clock.now(),
        outcome=ExecutionOutcome(
            output="y",
            latency_ms=5.0,
            tokens=TokenUsage(input_tokens=2, output_tokens=3),
        ),
        failure=None,
        evidence_references=(),
    )


@pytest.fixture
def metric_result(clock: FrozenClock) -> MetricResult:
    return MetricResult(
        id="mtr:1",
        run_id="run:1",
        execution_id="exe:1",
        test_case_id="tc:1",
        metric_name="exact_match",
        score=1.0,
        evaluator_identity="aegis/deterministic/exact_match",
        evaluator_version="1.0",
        created_at=clock.now(),
        evidence=(
            EvidenceReference(
                execution_id="exe:1",
                dataset_case_id="tc:1",
                trace_artifact_id="trace/1",
            ),
        ),
    )


def test_content_hash_is_stable_and_sensitive(clock: FrozenClock):
    cases = (AegisTestCase(id="tc", dataset_version_id="dv", index=0, input="a", expected="b"),)
    first = content_hash(cases)
    second = content_hash(cases)
    assert first == second
    different = (AegisTestCase(id="tc", dataset_version_id="dv", index=0, input="a", expected="c"),)
    assert content_hash(different) != first


def test_build_provenance_snapshot(clock, experiment, target_version, dataset_version):
    snapshot = build_provenance(
        clock,
        experiment,
        target_version,
        dataset_version,
        ("aegis/deterministic/exact_match",),
        None,
    )
    assert isinstance(snapshot, ProvenanceSnapshot)
    assert snapshot.experiment_id == "exp:1"
    assert snapshot.dataset_hash == content_hash(dataset_version.test_cases)
    assert snapshot.evaluator_identities == ("aegis/deterministic/exact_match",)


def test_build_evidence_record_links_metric(
    clock, experiment, target_version, dataset_version, execution, metric_result
):
    provenance = build_provenance(
        clock,
        experiment,
        target_version,
        dataset_version,
        ("aegis/deterministic/exact_match",),
        None,
    )
    record = build_evidence_record(
        clock,
        metric_result,
        execution,
        experiment,
        target_version,
        dataset_version,
        provenance,
        created_by="alice",
        classification=DataClassification.INTERNAL,
    )
    assert isinstance(record, EvidenceRecord)
    assert record.metric_result_id == "mtr:1"
    assert record.run_id == "run:1"
    assert record.experiment_id == "exp:1"
    assert record.evaluator_identity == "aegis/deterministic/exact_match"
    assert record.created_by == "alice"
    assert record.provenance is provenance


def test_build_evidence_record_rejects_mismatched_execution(
    clock, experiment, target_version, dataset_version, metric_result, execution
):
    from aegis.domain.results import EvidenceViolation

    stray = ExecutionRecord(
        id="exe:other",
        run_id="run:1",
        sequence=1,
        test_case_id="tc:1",
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        status=ExecutionStatus.SUCCEEDED,
        created_at=clock.now(),
        outcome=ExecutionOutcome(output="z", latency_ms=1.0, tokens=TokenUsage()),
    )
    provenance = build_provenance(
        clock,
        experiment,
        target_version,
        dataset_version,
        ("aegis/deterministic/exact_match",),
        None,
    )
    with pytest.raises(EvidenceViolation):
        build_evidence_record(
            clock,
            metric_result,
            stray,
            experiment,
            target_version,
            dataset_version,
            provenance,
        )


def test_link_evidence_to_score_persists_once(
    clock, experiment, target_version, dataset_version, execution, metric_result
):
    repository = MemoryEvidenceRepository()
    record = link_evidence_to_score(
        repository, clock, metric_result, execution, experiment, target_version, dataset_version
    )
    assert repository.exists(record.id)
    assert repository.get(record.id) is record


def test_evidence_repository_write_once(
    clock, experiment, target_version, dataset_version, execution, metric_result
):
    repository = MemoryEvidenceRepository()
    record = link_evidence_to_score(
        repository, clock, metric_result, execution, experiment, target_version, dataset_version
    )
    with pytest.raises(Conflict):
        repository.persist(record)
    assert len(repository.list_for_run("run:1")) == 1
    assert len(repository.list_for_metric_result("mtr:1")) == 1
    with pytest.raises(NotFound):
        repository.get("missing")


def test_provenance_index_lookup(
    clock, experiment, target_version, dataset_version, execution, metric_result
):
    record = build_evidence_record(
        clock,
        metric_result,
        execution,
        experiment,
        target_version,
        dataset_version,
        build_provenance(
            clock,
            experiment,
            target_version,
            dataset_version,
            ("aegis/deterministic/exact_match",),
            None,
        ),
    )
    index = MemoryProvenanceIndex()
    index.index(record)
    assert index.provenance_for_execution("exe:1").experiment_id == "exp:1"
    assert index.provenance_for_result("mtr:1").dataset_version_id == "dsv:1"
    with pytest.raises(NotFound):
        index.provenance_for_result("missing")


def test_artifact_manager_store_retrieve_delete():
    manager = MemoryArtifactManager()
    reference = manager.store(
        ArtifactType.RAW_OUTPUT,
        b"hello",
        {"content_type": "text/plain"},
    )
    assert isinstance(reference, ArtifactReference)
    assert reference.size_bytes == 5
    assert manager.retrieve(reference.artifact_id) == b"hello"
    assert manager.get_reference(reference.artifact_id).content_hash == reference.content_hash
    manager.delete(reference.artifact_id)
    with pytest.raises(NotFound):
        manager.retrieve(reference.artifact_id)


def test_evidence_graph_traversal():
    graph = InMemoryEvidenceGraph()
    graph.add_edge(EvidenceEdge("experiment", "exp:1", "run", "run:1", EdgeType.PRODUCED_BY))
    graph.add_edge(EvidenceEdge("run", "run:1", "execution", "exe:1", EdgeType.CONTAINS))
    result = graph.query(EvidenceGraphQuery("experiment", "exp:1", depth=2))
    assert len(result.nodes) == 3
    assert len(result.edges) == 2
    assert all(n.entity_id in {"exp:1", "run:1", "exe:1"} for n in result.nodes)
    assert graph.edges_for("run", "run:1")


def test_evidence_graph_is_append_only():
    graph = InMemoryEvidenceGraph()
    from aegis.domain import ImmutableResourceViolation

    with pytest.raises(ImmutableResourceViolation):
        graph.remove_node("experiment", "exp:1")


def test_evidence_graph_respects_depth_and_edge_filter():
    graph = InMemoryEvidenceGraph()
    graph.add_edge(EvidenceEdge("experiment", "exp:1", "run", "run:1", EdgeType.PRODUCED_BY))
    graph.add_edge(EvidenceEdge("run", "run:1", "execution", "exe:1", EdgeType.CONTAINS))
    result = graph.query(
        EvidenceGraphQuery(
            "experiment",
            "exp:1",
            depth=1,
            edge_types=(EdgeType.PRODUCED_BY,),
        )
    )
    assert len(result.edges) == 1


def test_run_with_evidence_summary_roundtrips(clock: FrozenClock):
    snapshot = ExperimentSnapshot(
        target_version_id="tvr:1",
        dataset_version_id="dsv:1",
        evaluator_version_ids=("aegis/deterministic/exact_match",),
    )
    run = run_created(clock, "org:1", "prj:1", "exp:1", snapshot, created_by="alice")
    assert run.id.startswith("run:")
    assert run.experiment_id == "exp:1"


__all__ = []
