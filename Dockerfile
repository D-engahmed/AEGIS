# AEGIS - AI Evaluation, Reliability & Observability Platform
# Production image. Builds the aegis package and verifies the installed
# distribution before the final runtime stage.

FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build dependencies first so re-installs are cheap.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip wheel --no-deps --wheel-dir /build/dist .

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AEGIS_ENV=production

WORKDIR /app

# System deps kept minimal and pinned to 3.12-slim's latest available.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/dist /app/dist

RUN pip install --no-cache-dir /app/dist/aegis-*.whl \
    && rm -rf /app/dist

COPY docker/entrypoint.sh /usr/local/bin/aegis-entrypoint
RUN chmod +x /usr/local/bin/aegis-entrypoint

# Import + version smoke test at build time so a broken install never ships.
RUN python -c "import aegis; print('aegis', aegis.__version__, 'ok')"

# Non-root user for defense in depth.
RUN useradd --create-home --uid 10001 aegis
USER aegis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["aegis-entrypoint", "probe"]

ENTRYPOINT ["aegis-entrypoint"]
