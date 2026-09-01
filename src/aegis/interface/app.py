"""FastAPI application factory for the AEGIS HTTP interface (layer 03).

Composes the container, registers routers and exception handlers, and exposes
`create_app()` plus a module-level `app` for ASGI servers (uvicorn, Docker).
"""

from __future__ import annotations

from fastapi import FastAPI

from .container import Container
from .errors import register_exception_handlers
from .routers.analysis import router as analysis_router
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

    app.include_router(experiments_router)
    app.include_router(runs_router)
    app.include_router(evidence_router)
    app.include_router(analysis_router)
    app.include_router(security_router)
    app.include_router(policy_router)
    app.include_router(observability_router)
    app.include_router(health_router)

    register_exception_handlers(app)
    return app


app = create_app()

__all__ = ["create_app"]
