# Dependency Rules

Every dependency in the AEGIS codebase is chosen once, justified, documented, and never introduced ad hoc. This file is the authoritative registry.

## Authorized Dependencies by Layer

### Layer 01: Domain

The domain layer has **zero external framework dependencies**. Only Python standard library conventions are permitted. No ORM, no HTTP libs, no queue libs, no provider SDKs, no LLM client libraries.

Forbidden imports in domain code (verbatim):

```
HTTP
SQL
Redis
FastAPI
Django
Celery
Provider SDK
```

### Layer 02: Application

- Domain layer (01).
- Pydantic (for DTOs and input validation schemas).
- Transaction and unit-of-work abstractions (interface only, not concrete implementation).

### Layer 03: Interface

- FastAPI (REST API framework).
- Pydantic (request/response schemas).
- Auth middleware (from security layer 11).
- Application layer (02).

### Layer 04: Infrastructure

- SQLAlchemy (ORM for PostgreSQL).
- Redis client (queue, cache, distributed locks).
- Object storage client (S3-compatible).
- OpenTelemetry SDK (tracing, metrics).
- Secrets provider client (Vault, cloud KMS).
- HTTP clients (httpx, aiohttp).
- External API clients only when implementing an application-layer interface.

### Layer 05: Execution

- Queue client (Celery, Dramatiq, or ARQ).
- Sandboxing libraries (for isolated target execution).
- Application layer (02).

### Layer 06: Evaluation

- Evaluator plugin SDK (AEGIS internal).
- LLM provider SDKs (for judge-based evaluation only, within the evaluator plugin boundary).
- Embedding model clients (for semantic metrics).
- Application layer (02).

### Layers 07-11

Dependencies for these layers are established as they are implemented and will be recorded here with the same rigor.

## Procedure for Adding a Dependency

1. **Justify**: State the problem the dependency solves. Why is stdlib insufficient?
2. **Check alternatives**: List at least two alternatives considered, including not adding the dependency.
3. **Record**: Add the dependency to this file under the correct layer with a one-line justification.
4. **Verify**: Ensure the license is compatible (Apache-2.0, MIT, BSD, or equivalent). Run a security scan.
5. **ADR**: If the dependency introduces a new architectural pattern or crosses layer boundaries, record an ADR.

## Principles

- A dependency is chosen once per purpose. Do not introduce two libraries that solve the same problem.
- Prefer the standard library over external packages.
- Prefer well-maintained, widely-adopted packages over niche alternatives.
- Pin versions in lock files. Do not use floating ranges in production dependencies.
- Review transitive dependencies. A small direct dependency with heavy transitive weight may not be "small."
