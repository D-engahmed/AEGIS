"""Dependency container: wiring of application services and adapters.

The interface layer composes concrete infrastructure (in-memory adapters) with
application services and cross-cutting security/evidence/analysis/observability
components. A single Container instance is shared by the FastAPI app so tests
can build a fresh one per test.
"""

from __future__ import annotations

import os

from aegis.analysis.clustering import CategoryFailureClassifier
from aegis.analysis.comparison import WelchExperimentComparator
from aegis.analysis.regression import WelchRegressionDetector
from aegis.analysis.slicing import DimensionSlicer
from aegis.analysis.trends import LinearTrendAnalyzer
from aegis.application.ports import (
    CancellationRegistry,
    DataCatalog,
    ExecutionRepository,
    ExperimentRepository,
    Queue,
    ResultRepository,
    RunRepository,
)
from aegis.application.run_gates import RunGateService
from aegis.application.runner import EvaluationRunner
from aegis.application.services import ExperimentService, RunService
from aegis.domain.time import Clock, SystemClock
from aegis.evidence.graph import InMemoryEvidenceGraph
from aegis.evidence.ports import ArtifactManager, EvidenceRepository, ProvenanceQuery
from aegis.infrastructure.memory import (
    InMemoryCancellationRegistry,
    InMemoryDataCatalog,
    MemoryArtifactManager,
    MemoryEvidenceRepository,
    MemoryExecutionRepository,
    MemoryExperimentRepository,
    MemoryProvenanceIndex,
    MemoryQueue,
    MemoryResultRepository,
    MemoryRunGateStore,
    MemoryRunRepository,
)
from aegis.observability.cost import InMemoryCostTracker
from aegis.observability.health import HealthAggregator, StaticHealthCheck
from aegis.observability.models import HealthStatus
from aegis.observability.preservation import TracePreservationEngine
from aegis.observability.run_tracing import EvaluationTracerProvider
from aegis.observability.tracing import InMemoryExporter, InMemoryTracerProvider
from aegis.policy.application import Gate
from aegis.policy.ports import RunGateStore
from aegis.security.audit import InMemorySecretsProvider, MemoryAuditLogger
from aegis.security.auth import HmacTokenAuthProvider
from aegis.security.pii import DefaultClassificationAnnotator, RegexPIIDetector
from aegis.security.rbac import RBACPermissionChecker

AUTH_SECRET = "dev-only-secret-change-me"

_UNSET = object()


class Container:
    """Holds every collaborator the HTTP application needs."""

    @classmethod
    def from_env(
        cls,
        clock: Clock | None = None,
        *,
        gates: tuple[Gate, ...] = (),
        database_url=_UNSET,
        redis_url=_UNSET,
        migrate: bool = True,
    ) -> Container:
        """Build from environment; explicit kwargs win over env vars.

        ``AEGIS_DATABASE_URL`` / ``AEGIS_REDIS_URL`` select PostgreSQL/Redis
        adapters; when unset the in-memory defaults are used so the tool works
        without infrastructure. Pass ``None`` explicitly to force in-memory.
        """
        use_db = os.environ.get("AEGIS_DATABASE_URL") if database_url is _UNSET else database_url
        use_redis = os.environ.get("AEGIS_REDIS_URL") if redis_url is _UNSET else redis_url
        return cls(
            clock,
            gates=gates,
            database_url=use_db,
            redis_url=use_redis,
            migrate=migrate,
        )

    def __init__(
        self,
        clock: Clock | None = None,
        *,
        gates: tuple[Gate, ...] = (),
        database_url: str | None = None,
        redis_url: str | None = None,
        migrate: bool = True,
    ) -> None:
        self.clock = clock or SystemClock()

        self.experiments: ExperimentRepository
        self.runs: RunRepository
        self.executions: ExecutionRepository
        self.results: ResultRepository
        self.catalog: DataCatalog
        self.cancellations: CancellationRegistry
        self.run_gate_store: RunGateStore
        self.evidence_repository: EvidenceRepository
        self.provenance: ProvenanceQuery
        self.artifacts: ArtifactManager
        self.queue: Queue

        if database_url is not None:
            from aegis.infrastructure.postgres import PostgresStore

            self.stores = PostgresStore(database_url)
            if migrate:
                self.stores.migrate()
            self.experiments = self.stores.experiments
            self.runs = self.stores.runs
            self.executions = self.stores.executions
            self.results = self.stores.results
            self.catalog = self.stores.catalog
            self.cancellations = self.stores.cancellations
            self.run_gate_store = self.stores.run_gate_store
            self.evidence_repository = self.stores.evidence
            self.provenance = self.stores.provenance
            self.artifacts = self.stores.artifacts
        else:
            self.experiments = MemoryExperimentRepository()
            self.runs = MemoryRunRepository()
            self.executions = MemoryExecutionRepository()
            self.results = MemoryResultRepository()
            self.catalog = InMemoryDataCatalog()
            self.cancellations = InMemoryCancellationRegistry()
            self.run_gate_store = MemoryRunGateStore()
            self.evidence_repository = MemoryEvidenceRepository()
            self.provenance = MemoryProvenanceIndex()
            self.artifacts = MemoryArtifactManager()

        if redis_url is not None:
            from aegis.infrastructure.redis_queue import RedisQueue

            self.queue = RedisQueue(redis_url)
        else:
            self.queue = MemoryQueue()

        self.run_gates = RunGateService(self.run_gate_store, self.clock, gates=gates)

        self.experiment_service = ExperimentService(self.experiments, self.clock)
        self.run_service = RunService(
            self.experiments,
            self.runs,
            self.catalog,
            self.cancellations,
            self.queue,
            self.clock,
        )

        self.auth = HmacTokenAuthProvider(AUTH_SECRET)
        self.rbac = RBACPermissionChecker()
        self.audit = MemoryAuditLogger()
        self.pii = RegexPIIDetector()
        self.classifier = DefaultClassificationAnnotator(self.pii)
        self.secrets = InMemorySecretsProvider()

        self.evidence_graph = InMemoryEvidenceGraph()

        from aegis.application.evaluation import EvaluationService

        self.runner = EvaluationRunner(
            self.clock,
            experiments=self.experiments,
            runs=self.runs,
            executions=self.executions,
            results=self.results,
            catalog=self.catalog,
            cancellations=self.cancellations,
            queue=self.queue,
            evidence=self.evidence_repository,
            gateway=EvaluationService(self.clock),
            run_gates=self.run_gates,
        )

        self.failure_classifier = CategoryFailureClassifier()
        self.comparator = WelchExperimentComparator()
        self.regression = WelchRegressionDetector()
        self.slicer = DimensionSlicer()
        self.trends = LinearTrendAnalyzer(self.clock)

        self.tracer_provider = InMemoryTracerProvider(InMemoryExporter())
        self.preservation = TracePreservationEngine()
        self.evaluation_tracers = EvaluationTracerProvider(self.preservation)
        self.cost = InMemoryCostTracker()
        self.health = HealthAggregator(
            [
                StaticHealthCheck("api", HealthStatus.HEALTHY, "interface responding"),
                StaticHealthCheck(
                    "memory-adapters", HealthStatus.HEALTHY, "in-memory stores ready"
                ),
            ]
        )
