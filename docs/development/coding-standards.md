# Coding Standards

## Language

Python is the primary language. All new code must be written in Python unless a documented exception exists.

## Type Hints

Type hints are mandatory on all function signatures, return types, and class attributes. Use `typing` and `pydantic` types. No `Any` unless there is a documented reason.

## Docstrings

Every public function, class, and method must have a docstring. Docstrings describe what the code does, not how it does it. Internal helpers do not require docstrings.

## Exception Handling

No bare `except Exception` without classification. Every exception must be caught as a typed domain exception or explicitly re-raised. Swallowing exceptions is forbidden.

## Tests

Every module must have corresponding tests. Tests live in the same package or a parallel `tests/` directory. Test coverage for new code must not regress.

## Naming Conventions

- Functions and methods: `snake_case`.
- Classes: `PascalCase`.
- Domain entities: `PascalCase` nouns (`Experiment`, `TargetVersion`, `MetricResult`).
- Boolean variables and functions: `is_*`, `has_*`, `should_*`.
- Constants: `UPPER_SNAKE_CASE`.

## Immutability

Domain entities that represent historical records must be immutable after creation. Use frozen dataclasses or equivalent mechanisms. Mutable state is confined to application-layer services and infrastructure adapters.

## Async vs Sync

Use `async` for I/O-bound code in the interface and infrastructure layers (API handlers, database calls, HTTP clients, cache operations). Use synchronous code for CPU-bound domain logic and evaluation computation. The execution layer uses the async model dictated by its worker framework.

## Secrets and PII

Never log secrets, API keys, tokens, or personally identifiable information. Structured logging must redact sensitive fields. Secrets are accessed only through the secrets provider abstraction.

## Error Raising

Raise typed domain exceptions from application and domain code. Never raise raw `ValueError`, `RuntimeError`, or HTTP-specific exceptions from domain or application layers. The interface layer maps domain exceptions to transport codes.

## Git Conventions

- Commit messages follow conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Commits are atomic: one logical change per commit.
- Do not commit secrets, credentials, or PII.

## Lint and Format

- **Formatter**: Black (or Ruff formatter equivalent).
- **Linter**: Ruff with the project-configured rule set.
- **Type checker**: Pyright or mypy, strict mode where feasible.
- **Import sorting**: isort-compatible via Ruff.

Run the full lint and typecheck pipeline before marking any change complete. If the project has not yet configured these tools, the agent must flag this as a gap rather than skipping validation.
