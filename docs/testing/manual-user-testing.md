# Manual User Testing

## Purpose

Manual user testing is the human's verification of the full AEGIS scenario. Automated tests prove components and orchestration; the manual script proves the product from the perspective of the person who actually uses it, and produces evidence attached to a real run. Every manual test produces evidence — screenshots, recorded artifacts, run links — that must be attached to the run so the verdict is reproducible.

## Scenario Script

```text
1. Create Project
2. Create Target
3. Create Target Version
4. Create Dataset
5. Add Test Cases
6. Lock Dataset
7. Create Evaluator
8. Create Experiment
9. Run Experiment
10. Wait for completion
11. Inspect failure
12. Compare baseline
13. Trigger gate
14. Override if authorized
```

## Evidence Record

Each step records:

```text
Action
Expected Result
Invalid Result
What To Check
Screenshot/Evidence
```

- **Action**: exactly what the user does, as an executable instruction.
- **Expected Result**: what must happen when the action succeeds.
- **Invalid Result**: a concrete suspicious outcome that indicates a defect worth escalating, not just "anything else."
- **What To Check**: the specific things to verify that a quick glance misses.
- **Screenshot/Evidence**: the artifact that must be captured and attached to the run.

The tester works through all 14 steps in order and attaches the evidence to the run record so the run is auditable.

## Steps

### 1. Create Project

| Field | Guidance |
|---|---|
| Action | Create a project as a user with Engineer permissions. |
| Expected Result | Project created, owned by the organization and the creating identity, visible in project lists. |
| Invalid Result | Project appears in another tenant's list, is created without owner, or the create action succeeds without authorization. |
| What To Check | Organization and project scope on the project record; audit log records the create identity and timestamp. |
| Screenshot/Evidence | Project list with the new project; audit entry. |

### 2. Create Target

| Field | Guidance |
|---|---|
| Action | Create a target under the project (for example, a black-box HTTP target). |
| Expected Result | Target created with an ID and placeholder configuration; no secret material stored in the target record. |
| Invalid Result | Target leaks provider configuration secrets into metadata or allows setting a secret as a plain value. |
| What To Check | Target record references secrets by reference, never by value; target scoped to the project. |
| Screenshot/Evidence | Target detail page; inspection of stored configuration for secret leakage. |

### 3. Create Target Version

| Field | Guidance |
|---|---|
| Action | Create a target version with model, provider, and configuration pinned. |
| Expected Result | Target version created and immutable; configuration snapshot captured. |
| Invalid Result | The version record changes after creation, or configuration can be edited in place. |
| What To Check | Immutability enforced; version identifies code, model, prompt, and environment provenance. |
| Screenshot/Evidence | Target version page; attempted edit of the immutable version fails. |

### 4. Create Dataset

| Field | Guidance |
|---|---|
| Action | Create a dataset and upload a versioned set of test cases. |
| Expected Result | Dataset created as a versioned collection of scenarios; dataset quality checks available. |
| Invalid Result | Dataset accepted with duplicate cases, no coverage, or cases from outside the tenant. |
| What To Check | Dataset version recorded; quality report available (duplicates, leakage, coverage, imbalance). |
| Screenshot/Evidence | Dataset page with version; dataset quality report. |

### 5. Add Test Cases

| Field | Guidance |
|---|---|
| Action | Add test cases covering normal, edge, invalid, and adversarial inputs. |
| Expected Result | Each test case is added with its expected output, expected tool calls, or golden reference where applicable. |
| Invalid Result | Test cases silently added without expected values, or golden references stored as secrets. |
| What To Check | Test-case inputs and expected outputs visible; classification per test case; no real secrets or PII in test data. |
| Screenshot/Evidence | Test case list with expected values; a representative edge-case and adversarial case. |

### 6. Lock Dataset

| Field | Guidance |
|---|---|
| Action | Lock the dataset version. |
| Expected Result | Lock succeeds; the dataset version becomes immutable; further edits are rejected. |
| Invalid Result | Locked dataset can be edited, or an experiment runs against an unlocked dataset that later changes meaning. |
| What To Check | Lock persisted; edit attempts rejected; experiments reference the locked version. |
| Screenshot/Evidence | Locked dataset state; rejected edit attempt with error. |

### 7. Create Evaluator

| Field | Guidance |
|---|---|
| Action | Create an evaluator by choosing an evaluator plugin and configuration. |
| Expected Result | Evaluator created behind a validated interface (`evaluate`, `validate`, `metadata`); its `validate()` passes. |
| Invalid Result | Evaluator accepted with an invalid configuration, or the evaluator version is not recorded. |
| What To Check | Evaluator identity and version recorded; judge model and judge prompt version captured for LLM-judge evaluators. |
| Screenshot/Evidence | Evaluator detail page showing identity, version, and judge provenance. |

### 8. Create Experiment

| Field | Guidance |
|---|---|
| Action | Create an experiment binding the target version, locked dataset, evaluators, and gate policy. |
| Expected Result | Experiment created and immutable once running; configuration fully captured. |
| Invalid Result | Experiment mutates after creation, or an impossible combination is accepted. |
| What To Check | Experiment references locked dataset version; configuration versioned; gate policy attached. |
| Screenshot/Evidence | Experiment configuration page. |

### 9. Run Experiment

| Field | Guidance |
|---|---|
| Action | Start the experiment run. |
| Expected Result | Run is queued and becomes the current execution with a unique execution identity. |
| Invalid Result | Run starts without a pending state, is created without tenant scope, or duplicates an existing run. |
| What To Check | Run resource created with execution ID and idempotency key; status transitions recorded. |
| Screenshot/Evidence | Run creation response with execution ID; run appearing in the run list. |

### 10. Wait for Completion

| Field | Guidance |
|---|---|
| Action | Wait for the run to reach a terminal state. |
| Expected Result | Run reaches terminal state; results, evidence, and verdict are available for inspection. |
| Invalid Result | Run hangs in queued or running beyond its timeout, or a timeout is reported without timeout context. |
| What To Check | Terminal state recorded (succeeded, failed, partial, cancelled); each state distinguishable; user notified on failure or cancellation. |
| Screenshot/Evidence | Run status page; terminal-state record; notification if applicable. |

### 11. Inspect Failure

| Field | Guidance |
|---|---|
| Action | Open a failed test case and inspect its failure. |
| Expected Result | The failure is classified (model, retrieval, tool, agent loop, timeout, validation) with evidence and trace attached. |
| Invalid Result | Failure shows a score with no evidence, or a failure class that contradicts the evidence. |
| What To Check | Execution, trace, tool calls, retrieval, and errors visible; score carries evaluator and confidence provenance; partial evidence preserved. |
| Screenshot/Evidence | Failure detail with trace and evidence; failure-clustering view. |

### 12. Compare Baseline

| Field | Guidance |
|---|---|
| Action | Compare the run against a baseline target version. |
| Expected Result | Per-test-case comparison view shows which cases regressed, improved, or stayed the same, with slice breakdowns. |
| Invalid Result | Only aggregate scores shown, or a small aggregate delta is presented as meaningful without statistical context. |
| What To Check | Per-test comparison beats aggregates; sample size and significance noted; sliced reporting present; safety regressions flagged non-compensatory. |
| Screenshot/Evidence | Comparison view; a regressed test case with per-case evidence. |

### 13. Trigger Gate

| Field | Guidance |
|---|---|
| Action | Trigger the deployment gate against the run's results and policy. |
| Expected Result | Gate produces a verdict: pass, warn, or block, computed from policy, severity, and thresholds. |
| Invalid Result | Gate passes despite a critical safety failure, or recommends compensation of a safety regression by a quality gain. |
| What To Check | Verdict computed non-compensatory; blocking metrics enforce; verdict references the evidence it was computed from. |
| Screenshot/Evidence | Gate verdict with policy and evidence reference. |

### 14. Override if Authorized

| Field | Guidance |
|---|---|
| Action | If the gate is blocked and the override is authorized, perform the override. |
| Expected Result | Override succeeds only for an authorized identity; the override is recorded with identity, time, and reason; failing the gate never becomes invisible. |
| Invalid Result | Unauthorized override succeeds, or the audit record is missing or silent. |
| What To Check | Audit log records the override; the blocked state remains visible in reporting; cancelled work distinct from failed work. |
| Screenshot/Evidence | Override action; audit entry with identity, timestamp, and reason. |