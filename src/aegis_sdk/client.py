"""Synchronous HTTP client for the AEGIS API.

``AegisClient`` talks to a running AEGIS server over bearer-token
authentication. It exposes typed resource clients (catalog, experiments, runs,
analysis, policy, observability, security, evaluators) whose methods map 1:1 to
the REST contract in ``docs/api/``.

The transport is injectable: pass an ``httpx.ASGITransport`` or a ``MockTransport``
to exercise the client against an in-process app in tests.
"""

from __future__ import annotations

from typing import Any

import httpx

from .errors import AegisErrorMapping
from .models import (
    CatalogDataset,
    CatalogSummary,
    CatalogTarget,
    EvaluatorSpec,
    Experiment,
    GateReport,
    HealthSummary,
    MetricResult,
    Run,
    Token,
    TrendReport,
)

_TYPED = (
    CatalogDataset,
    CatalogSummary,
    CatalogTarget,
    EvaluatorSpec,
    Experiment,
    GateReport,
    HealthSummary,
    MetricResult,
    Run,
    Token,
    TrendReport,
)


class _Resource:
    """Mixin: shared request plumbing for resource sub-clients."""

    def __init__(self, client: AegisClient) -> None:
        self._client = client

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return self._client.request(method, path, **kwargs)


class CatalogResource(_Resource):
    """Registered target/dataset versions within the tenant."""

    def all(self) -> CatalogSummary:
        return CatalogSummary.parse(self._request("GET", "/catalog"))

    def targets(self) -> list[CatalogTarget]:
        return _parse_list(CatalogTarget, self._request("GET", "/catalog/targets"))

    def datasets(self) -> list[CatalogDataset]:
        return _parse_list(CatalogDataset, self._request("GET", "/catalog/datasets"))

    def get_target(self, target_version_id: str) -> CatalogTarget:
        return CatalogTarget.parse(
            self._request("GET", f"/catalog/targets/{_quote(target_version_id)}")
        )

    def get_dataset(self, dataset_version_id: str) -> CatalogDataset:
        return CatalogDataset.parse(
            self._request("GET", f"/catalog/datasets/{_quote(dataset_version_id)}")
        )

    def register_target(
        self,
        project_id: str,
        name: str,
        *,
        target_type: str = "llm_application",
        label: str = "1.0.0",
        config: dict[str, Any] | None = None,
        commit_sha: str | None = None,
    ) -> CatalogTarget:
        return CatalogTarget.parse(
            self._request(
                "POST",
                "/catalog/targets",
                json={
                    "project_id": project_id,
                    "name": name,
                    "target_type": target_type,
                    "label": label,
                    "config": config or {},
                    "commit_sha": commit_sha,
                },
            )
        )

    def register_dataset(
        self,
        project_id: str,
        name: str,
        *,
        label: str = "1.0.0",
        test_cases: list[dict[str, Any]] | None = None,
    ) -> CatalogDataset:
        return CatalogDataset.parse(
            self._request(
                "POST",
                "/catalog/datasets",
                json={
                    "project_id": project_id,
                    "name": name,
                    "label": label,
                    "test_cases": test_cases or [],
                },
            )
        )


class ExperimentsResource(_Resource):
    """Reproducible evaluation configurations."""

    def all(self) -> list[Experiment]:
        return _parse_list(Experiment, self._request("GET", "/experiments"))

    def get(self, experiment_id: str) -> Experiment:
        return Experiment.parse(
            self._request("GET", f"/experiments/{_quote(experiment_id)}")
        )

    def create(
        self,
        project_id: str,
        name: str,
        snapshot: dict[str, Any],
    ) -> Experiment:
        return Experiment.parse(
            self._request(
                "POST",
                "/experiments",
                json={"project_id": project_id, "name": name, "snapshot": snapshot},
            )
        )

    def clone(self, experiment_id: str) -> Experiment:
        return Experiment.parse(
            self._request("POST", f"/experiments/{_quote(experiment_id)}/clone")
        )

    def start(self, experiment_id: str) -> Experiment:
        return Experiment.parse(
            self._request("POST", f"/experiments/{_quote(experiment_id)}/start")
        )

    def runs(self, experiment_id: str) -> list[Run]:
        return _parse_list(
            Run, self._request("GET", f"/experiments/{_quote(experiment_id)}/runs")
        )


class RunsResource(_Resource):
    """Asynchronous executions of experiments."""

    def all(self, *, experiment_id: str | None = None, limit: int = 50) -> list[Run]:
        params: dict[str, Any] = {"limit": limit}
        if experiment_id is not None:
            params["experiment_id"] = experiment_id
        return _parse_list(Run, self._request("GET", "/runs", params=params))

    def get(self, run_id: str) -> Run:
        return Run.parse(self._request("GET", f"/runs/{_quote(run_id)}"))

    def submit(
        self,
        experiment_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> Run:
        return Run.parse(
            self._request(
                "POST",
                "/runs",
                json={"experiment_id": experiment_id, "idempotency_key": idempotency_key},
            )
        )

    def cancel(self, run_id: str) -> Run:
        return Run.parse(self._request("POST", f"/runs/{_quote(run_id)}/cancel"))

    def results(self, run_id: str, *, metric_name: str | None = None) -> list[MetricResult]:
        params = {"metric_name": metric_name} if metric_name else None
        return _parse_list(
            MetricResult, self._request("GET", f"/runs/{_quote(run_id)}/results", params=params)
        )

    def cancel_and_wait(self, run_id: str) -> Run:
        """Cancel a run, then block until the server reports a terminal state."""
        run = self.cancel(run_id)
        while not run.terminal:
            run = self.get(run_id)
        return run


class AnalysisResource(_Resource):
    """Reports computed over persisted metric results.

    ``regression``, ``compare`` and ``failures`` return raw JSON objects since
    their wire shape is defined by the current API server version.
    """

    def trend(self, metric_name: str, run_ids: list[str]) -> TrendReport:
        params = [("run_ids", run_id) for run_id in run_ids]
        return TrendReport.parse(
            self._request("GET", f"/analysis/trend/{_quote(metric_name)}", params=params)
        )

    def regression(
        self,
        baseline_run_id: str,
        current_run_id: str,
        *,
        significance_level: float = 0.05,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/analysis/regression",
            params={
                "baseline_run_id": baseline_run_id,
                "current_run_id": current_run_id,
                "significance_level": significance_level,
            },
        )

    def compare(
        self,
        run_ids_a: list[str],
        run_ids_b: list[str],
    ) -> dict[str, Any]:
        params = [("run_ids_a", rid) for rid in run_ids_a] + [
            ("run_ids_b", rid) for rid in run_ids_b
        ]
        return self._request("GET", "/analysis/compare", params=params)

    def failures(self, run_ids: list[str]) -> list[dict[str, Any]]:
        params = [("run_ids", rid) for rid in run_ids]
        return self._request("GET", "/analysis/failures", params=params)


class PolicyResource(_Resource):
    """Run gate verdicts and authorized overrides."""

    def verdict(self, run_id: str) -> GateReport:
        return GateReport.parse(self._request("GET", f"/policy/verdict/{_quote(run_id)}"))

    def override(self, run_id: str, reason: str) -> GateReport:
        return GateReport.parse(
            self._request(
                "POST",
                f"/policy/verdict/{_quote(run_id)}/override",
                json={"reason": reason},
            )
        )


class ObservabilityResource(_Resource):
    """Cost and preserved evaluation traces."""

    def run_cost(self, run_id: str) -> dict[str, float]:
        return self._request("GET", f"/observability/cost/{_quote(run_id)}")

    def run_traces(self, run_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/observability/traces/{_quote(run_id)}")

    def live(self) -> HealthSummary:
        return HealthSummary.parse(self._request("GET", "/health/live"))


class SecurityResource(_Resource):
    """Token issuance, PII redaction, and the audit trail."""

    def issue_token(self) -> Token:
        return Token.parse(self._request("POST", "/security/tokens"))

    def redact_pii(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/security/pii/redact", json={"text": text})

    def audit(
        self,
        *,
        actor_id: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {}
        if actor_id is not None:
            params["actor_id"] = actor_id
        if resource_type is not None:
            params["resource_type"] = resource_type
        return self._request("GET", "/security/audit", params=params or None)


class EvaluatorsResource(_Resource):
    """Scoring plugin discovery (deterministic + trajectory)."""

    def all(self) -> list[EvaluatorSpec]:
        return _parse_list(EvaluatorSpec, self._request("GET", "/evaluators"))


class AegisClient:
    """Bearer-authenticated client for the AEGIS REST API.

    The HTTP layer is injectable: pass ``http`` (any object with a
    ``request(method, url, **kwargs)`` method returning a response with
    ``status_code``, ``text``, ``content`` and ``json()``, plus a ``close()``
    method) to exercise the client against an in-process app, for example a
    ``fastapi.testclient.TestClient``. Without it, a plain ``httpx.Client`` is
    constructed (optionally with a custom ``transport``).
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        http: Any | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._headers = {"Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        if http is not None:
            self._http = http
            self._owns_http = False
        else:
            self._http = httpx.Client(
                base_url=base_url.rstrip("/"),
                headers=dict(self._headers),
                timeout=timeout,
                transport=transport,
            )
            self._owns_http = True
        self.catalog = CatalogResource(self)
        self.experiments = ExperimentsResource(self)
        self.runs = RunsResource(self)
        self.analysis = AnalysisResource(self)
        self.policy = PolicyResource(self)
        self.observability = ObservabilityResource(self)
        self.security = SecurityResource(self)
        self.evaluators = EvaluatorsResource(self)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._headers:
            merged = dict(self._headers)
            merged.update(kwargs.pop("headers", {}) or {})
            kwargs["headers"] = merged
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            detail = response.text
            try:
                body = response.json()
                detail = body.get("detail") or detail
            except ValueError:
                pass
            error_type = AegisErrorMapping.for_status(response.status_code)
            raise error_type(f"{method} {path} -> {response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> AegisClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _parse_list(model_type, items: list[Any]) -> list[Any]:
    return [model_type.parse(item) for item in items]


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value), safe="")


__all__ = [
    "AegisClient",
    "AnalysisResource",
    "CatalogResource",
    "EvaluatorsResource",
    "ExperimentsResource",
    "ObservabilityResource",
    "PolicyResource",
    "RunsResource",
    "SecurityResource",
]