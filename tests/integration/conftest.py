"""Live-service fixtures for AEGIS integration tests (marker: integration).

PostgreSQL and Redis come from `docker compose up -d postgres redis`. Tests
self-skip when the services are unreachable, so the suite still runs on
machines without Docker.
"""

from __future__ import annotations

import os

import psycopg
import pytest
import redis as redis_lib

from aegis.infrastructure.migrations import apply_migrations

pytestmark = pytest.mark.integration


def _dsn() -> str:
    return os.environ.get("AEGIS_DATABASE_URL", "postgresql://aegis:aegis@127.0.0.1:5433/aegis")


def _redis_url() -> str:
    return os.environ.get("AEGIS_REDIS_URL", "redis://127.0.0.1:6380/0")


def _reset_schema(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
    apply_migrations(dsn)


@pytest.fixture
def database_url() -> str:
    dsn = _dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.close()
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unreachable at {dsn}; run `docker compose up -d postgres`")
    _reset_schema(dsn)
    return dsn


@pytest.fixture
def redis_url() -> str:
    url = _redis_url()
    client = redis_lib.Redis.from_url(url)
    try:
        client.ping()
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip(f"Redis unreachable at {url}; run `docker compose up -d redis`")
    client.flushdb()
    return url
