# Unit Testing

## Scope

Unit tests cover the pure reasoning of the control plane. They verify that a rule, a policy, a gate, or a metric computation is correct when given a known input, in isolation from every real dependency.

```text
Domain Rules
Policies
Gate Logic
Retry Classification
Validation
Evaluator Logic
Statistics
```

Concretely:

- **Domain rules**: invariants for projects, targets, target versions, datasets, locked datasets, experiments, runs, and immutable records.
- **Policies**: permission composition, policy versioning, non-compensatory rule evaluation, and threshold logic.
- **Gate logic**: how a verdict (pass, warn, block, human override) is derived from results, policy, and severity.
- **Retry classification**: the mapping of failures to retryable, non-retryable, and deterministic classes, and the bounded-retry decision.
- **Validation**: schema validation, input robustness classification, identifier rules, and structured-output contract checks.
- **Evaluator logic**: deterministic metric computation, adapter translation, and score normalization.
- **Statistics**: aggregation, percentiles, slicing, confidence intervals, and regression math.

## What Unit Tests Run WITHOUT

Unit tests run without any real infrastructure or external service.

```text
Real Database
Real Redis
Real LLM
Real Provider
```

No unit test opens a PostgreSQL connection, reads or writes Redis, calls a model, or invokes a target provider. Anything that would require one of these is a faked port, an integration test, or a bug.

## Principles

### Pure Functions Preferred

Prefer logic that is a pure function of its inputs. Pure transitions are trivially testable, deterministic, and free of hidden state. Where a component must interact with the outside world, keep the interaction at the boundary and express the decision logic as a pure function that the boundary calls.

### Dependency Injection

Dependencies are injected, never imported and instantiated inside a unit. A component declares the ports it needs; tests supply fakes implementing those ports. This is what makes "no real database" enforceable rather than aspirational.

### Fakes for Ports

Repositories, queue clients, cache adapters, clocks, secrets managers, and provider clients are replaced with small in-memory fakes. A fake implements the port's contract and returns scripted results, which lets a unit test assert behavior on success, failure, and error paths without touching infrastructure.

### Coverage Policy

Coverage must not decrease beyond the policy threshold defined in the CI gates. The gate is enforced at `docs/ci-cd/pull-request-gates.md`. Coverage is a floor, not a goal: hitting the number does not excuse missing critical branches, and missing coverage on new logic fails the gate.

### Deterministic Tests Only

Unit tests are deterministic. The same code and the same inputs yield the same assertions every run. Avoid dependence on wall-clock time, random scheduling, locale, or environment-dependent behavior. Where randomness is part of production logic, inject the random source and control it in tests.

### No Sleeps or Fixed Timing as Synchronization

Do not use `sleep`, fixed delays, or timing loops to synchronize tests. A test must not race "until the code finishes"; it must observe the state transition that proves completion. If a component is asynchronous, wait on a deterministic signal: a callback, an event, a state change, or a faked clock. Timing-based synchronization invents flakiness and slow tests for no coverage gain.