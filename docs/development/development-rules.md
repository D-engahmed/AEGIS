# Global Development Rules

These rules apply to every change in the AEGIS repository. No exception. No "just this once."

## Dependency Direction

Dependencies flow toward the domain. The direction is strict:

- Interface calls application.
- Application calls domain.
- Infrastructure implements interfaces and depends upward toward domain, never inward toward concrete dependants.

No layer may reach across to a non-neighboring layer without an Architecture Decision Record (ADR) in `docs/architecture/architecture-decision-records/`. A jump from the interface directly to infrastructure, or from execution directly to policy authority, requires a recorded, justified decision.

## Domain Purity

Domain code has zero framework imports. It must not import HTTP, SQL, Redis, FastAPI, Django, Celery, or any provider SDK. The domain model is pure business logic and entities. Framework concerns belong to the interface, application, and infrastructure layers.

## Schema Changes

No schema change without a migration. Every database schema modification must be accompanied by a versioned migration script that can be applied and rolled back. Schema changes must be reviewed for backward compatibility with running code.

## API Changes

No API change without contract review. Adding, removing, or modifying endpoint signatures, request/response shapes, or status codes requires review against `docs/api/` contracts before implementation.

## Immutable Historical Data

No modification of immutable historical data. Historical dataset versions, evaluation results, experiment records, and evidence must never be altered after creation. Corrections are appended as new records.

## New Dependencies

No new dependency without documenting why. Every added dependency must follow this procedure:

1. Justify the need.
2. Check alternatives (including stdlib).
3. Record the choice in `docs/development/dependency-rules.md`.
4. Ensure license compatibility and security scan passes.
5. Record the decision in the ADR if the dependency introduces a new architectural pattern.

## Tests Are Mandatory

Every module must have tests. Tests are part of the implementation, not an afterthought. Code without tests is incomplete.

## Observability Must Be Added With Features

Every new feature, endpoint, or background job must include structured logging, metrics, and trace spans. Observability is not optional and is not added later.

## Security Is Every Layer's Concern

Security is a cross-cutting layer (11) that applies at every layer. No layer is exempt from considering authentication, authorization, tenancy isolation, and data classification.

## The Smallest Correct Change

Agents must make the smallest correct change that satisfies the requirements. Do not refactor unrelated code. Do not "improve" adjacent modules. Do not add features that were not requested. Scope creep is a defect.

## Code Review Expectations

Every change must be reviewable against these docs. A reviewer should be able to verify compliance by checking the relevant layer file and this document. If a change cannot be explained by referencing these docs, it is not ready for review.

## The Golden Rule

When in doubt, read the relevant docs file. Never invent rules, patterns, or conventions. The docs are authoritative. If the docs do not cover a case, escalate -- do not improvise.
