"""AEGIS Python SDK: typed client for the AEGIS REST API.

Usage::

    from aegis_sdk import AegisClient

    with AegisClient(base_url="https://aegis.example.com", token=api_token) as client:
        catalog = client.catalog.list()
        for target in catalog.targets:
            print(target.name, target.label)

Requires ``httpx`` (also a runtime dependency of the AEGIS server package).
"""

from .client import (
    AegisClient,
    AnalysisResource,
    CatalogResource,
    EvaluatorsResource,
    ExperimentsResource,
    ObservabilityResource,
    PolicyResource,
    RunsResource,
    SecurityResource,
)
from .errors import (
    AegisError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ServerError,
    ValidationError,
)
from .models import (
    ApiModel,
    CatalogDataset,
    CatalogSummary,
    CatalogTarget,
    EvaluatorSpec,
    Experiment,
    ExperimentSnapshot,
    GateDecision,
    GateReport,
    HealthCheck,
    HealthSummary,
    MetricResult,
    Run,
    Token,
    TrendPoint,
    TrendReport,
)

__version__ = "0.1.0"

__all__ = [
    "AegisClient",
    "AegisError",
    "AnalysisResource",
    "ApiModel",
    "AuthorizationError",
    "CatalogDataset",
    "CatalogResource",
    "CatalogSummary",
    "CatalogTarget",
    "ConflictError",
    "EvaluatorSpec",
    "EvaluatorsResource",
    "Experiment",
    "ExperimentSnapshot",
    "ExperimentsResource",
    "GateDecision",
    "GateReport",
    "HealthCheck",
    "HealthSummary",
    "MetricResult",
    "NotFoundError",
    "ObservabilityResource",
    "PolicyResource",
    "Run",
    "RunsResource",
    "SecurityResource",
    "ServerError",
    "Token",
    "TrendPoint",
    "TrendReport",
    "ValidationError",
]