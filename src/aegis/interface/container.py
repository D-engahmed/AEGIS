"""Dependency container: wiring of application services and adapters.

The interface layer composes concrete infrastructure (in-memory adapters) with
application services and cross-cutting security/evidence/analysis/observability
components. A single Container instance is shared by the FastAPI app so tests
can build a fresh one per test.
"""

from __future__ import annotations

from aegis.analysis.clustering import CategoryFailureClassifier
from aegis.analysis.comparison import WelchExperimentComparator
from aegis.analysis.regression import WelchRegressionDetector
from aegis.analysis.slicing import DimensionSlicer
from aegis.analysis.trends import LinearTrendAnalyzer
from aegis.application.run_gates import RunGateService
from aegis.application.services import ExperimentService, RunService
from aegis.domain.time import Clock, SystemClock
from aegis.evidence.graph import InMemoryEvidenceGraph
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
from aegis.security.audit import InMemorySecretsProvider, MemoryAuditLogger
from aegis.security.auth import HmacTokenAuthProvider
from aegis.security.pii import DefaultClassificationAnnotator, RegexPIIDetector
from aegis.security.rbac import RBACPermissionChecker

AUTH_SECRET = "dev-only-secret-change-me"


class Container:
    """Holds every collaborator the HTTP application needs."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()

        self.experiments = MemoryExperimentRepository()
        self.runs = MemoryRunRepository()
        self.executions = MemoryExecutionRepository()
        self.results = MemoryResultRepository()
        self.catalog = InMemoryDataCatalog()
        self.cancellations = InMemoryCancellationRegistry()
        self.queue = MemoryQueue()

        self.experiment_service = ExperimentService(self.experiments, self.clock)
        self.run_service = RunService(
            self.experiments,
            self.runs,
            self.catalog,
            self.cancellations,
            self.queue,
            self.clock,
        )

        self.run_gate_store = MemoryRunGateStore()
        self.run_gates = RunGateService(self.run_gate_store, self.clock)

        self.auth = HmacTokenAuthProvider(AUTH_SECRET)
        self.rbac = RBACPermissionChecker()
        self.audit = MemoryAuditLogger()
        self.pii = RegexPIIDetector()
        self.classifier = DefaultClassificationAnnotator(self.pii)
        self.secrets = InMemorySecretsProvider()

        self.evidence_repository = MemoryEvidenceRepository()
        self.provenance = MemoryProvenanceIndex()
        self.artifacts = MemoryArtifactManager()
        self.evidence_graph = InMemoryEvidenceGraph()

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
