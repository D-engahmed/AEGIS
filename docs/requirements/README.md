# Requirements Layer

## Purpose

The requirements layer answers only one question: **What must the system do?** It never answers "How will we implement it?" Implementation decisions belong to the Architecture layer. Requirements define intent; architecture defines structure; code defines behavior; tests verify correctness.

## Naming Convention

Every requirement carries a unique identifier following this scheme:

- **Functional Requirements**: `FR-<AREA>-NN` (e.g., `FR-EXE-01` for the first execution-area requirement).
- **Non-Functional Requirements**: `NFR-<AREA>-NN` (e.g., `NFR-PERF-01` for the first performance requirement).

The area code identifies the functional domain: `PRJ` (projects), `TGT` (targets), `DAT` (datasets), `EXP` (experiments), `EXE` (execution), `TRC` (tracing), `EVL` (evaluation), `ANA` (analysis), `POL` (policies), `EVD` (evidence), `SEC` (security), `OBS` (observability).

## The Testability Rule

Every requirement must be testable. If you cannot say how you will test a requirement, it is a weak or ambiguous requirement. A requirement without a test strategy is incomplete. This is not a suggestion; it is a gate. A requirement that cannot be tested will not be accepted into the specification.

## Traceability

Requirements trace downward through every layer of the system:

1. A **Functional Requirement** (e.g., `FR-EXE-03`) maps to an **Architecture Decision Record**.
2. The ADR maps to an **Architecture Component** (e.g., Execution Engine).
3. The component maps to a **Code Module** (e.g., `execution/retry/`).
4. The code module maps to a **Test Suite** (e.g., `test_retry_policy.py`).
5. The test suite maps to a **CI Gate** (e.g., `integration-test-job-retry`).

This chain is maintained in `docs/requirements/assumptions-and-constraints.md`. A requirement without a test is not done. A test without a CI gate is not enforced.

## Files in This Folder

| File | Description |
|---|---|
| `README.md` | This file. Layer purpose, naming conventions, testability rules, traceability concept. |
| `functional-requirements.md` | Functional requirements organized by area, with the 15-attribute template and worked examples. |
| `non-functional-requirements.md` | Non-functional requirements with the 8-attribute template: performance, availability, reliability, security, and more. |
| `acceptance-criteria.md` | Acceptance criteria that tell an agent when a feature is complete. |
| `assumptions-and-constraints.md` | Traceability matrix, architectural assumptions, and constraints that may not be revisited without an ADR. |
