"""FastAPI application factory for the AEGIS HTTP interface (layer 03).

Composes the container, registers routers and exception handlers, and exposes
`create_app()` plus a module-level `app` for ASGI servers (uvicorn, Docker).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .container import Container
from .errors import register_exception_handlers
from .routers.analysis import router as analysis_router
from .routers.catalog import router as catalog_router
from .routers.evaluators import router as evaluators_router
from .routers.evidence import router as evidence_router
from .routers.experiments import router as experiments_router
from .routers.observability import health_router
from .routers.observability import router as observability_router
from .routers.policy import router as policy_router
from .routers.runs import router as runs_router
from .routers.security import router as security_router

DESCRIPTION = (
    "AEGIS - AI Evaluation, Reliability & Observability Platform. "
    "Reproducible experiments, evidence-backed scores, and security "
    "for AI model evaluation workloads."
)


# The dashboard is a separate deployable (docs/architecture/container-
# architecture.md) that talks to the API over HTTP, so the API does not embed
# or serve UI assets. Cross-origin dashboard hosts opt in through
# AEGIS_CORS_ORIGINS (comma-separated origins); the default allows the
# conventional local development origins.
def _cors_origins() -> list[str]:
    if raw := os.environ.get("AEGIS_CORS_ORIGINS"):
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost", "http://127.0.0.1"]


def create_app(container: Container | None = None) -> FastAPI:
    """Build a configured FastAPI instance around an optional Container."""
    app = FastAPI(
        title="AEGIS API",
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.container = container or Container()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(experiments_router)
    app.include_router(runs_router)
    app.include_router(evidence_router)
    app.include_router(analysis_router)
    app.include_router(catalog_router)
    app.include_router(evaluators_router)
    app.include_router(security_router)
    app.include_router(policy_router)
    app.include_router(observability_router)
    app.include_router(health_router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """API self-description. The dashboard ships separately (frontend/)."""
        return {"service": "aegis-api", "docs": "/docs", "openapi": "/openapi.json"}

    register_exception_handlers(app)
    return app


app = create_app()

__all__ = ["create_app"]
