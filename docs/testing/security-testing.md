# Security Testing

## Purpose

Security in AEGIS is cross-cutting, and security testing proves the security architecture (`docs/architecture/security-architecture.md`) actually holds. AEGIS is itself a sensitive system: it stores evaluation data that can contain prompts, documents, PII, and traces; it executes work against targets; and it is multi-tenant. The security test program covers the control plane's own security and the security evaluation AEGIS runs against AI targets. The governing principle from `grilling.md`:

```text
Do not treat the LLM as a trusted security boundary.
Test the failure path before giving the agent real authority.
```

## Authentication and Authorization Abuse Tests

- Every endpoint is exercised without credentials, with invalid credentials, with expired credentials, and with revoked credentials. Unauthenticated and unauthorized access must fail.
- Permission tests attempt actions below a role's permission set: a Viewer creating an experiment, an Analyst modifying a target configuration, an Engineer accessing restricted raw traces. These attempts must fail.
- Service-account API keys are tested for scope enforcement, revocation, and rotation: a key scoped to one organization, project, environment, or target must not access anything outside its scope.
- All mutating calls pass the full write pipeline; authorization is re-checked at the application layer, never trusted only at the transport boundary.

## Tenant Isolation Tests

Cross-tenant access attempts MUST fail. The isolation tests verify at every layer that the application, database, storage, telemetry, and external integrations enforce tenancy:

- A user of tenant A cannot read, modify, or infer tenant B's projects, targets, datasets, experiments, runs, results, traces, or reports.
- Combined queries, batch endpoints, and list endpoints do not return cross-tenant rows.
- Object-storage artifacts are scoped to their organization and gated by authorization.
- PostgreSQL RLS (where enabled) is tested as a defense-in-depth layer: even if a query bypasses application scoping, the database layer refuses it.
- Cross-tenant memory leakage tests exercise targets with memory: user A's memory must never surface to user B, and one tenant's memory must never leak to another.
- Isolation is verified under load and during failure injection, not only at rest.

This enforces `NFR-SEC-01`: zero cross-tenant data leakage.

## Secrets Handling Tests

- Seed known secret patterns (API keys, tokens, connection strings) into model outputs, tool results, and trace content, then assert the pipeline detects, redacts, and alerts.
- Detection and redaction must occur before storage: stored traces and evaluation records must contain redaction markers, never the secret.
- The alert and security-incident flow must fire; a model accidentally outputting an API key is treated as a security incident per policy.
- Provider configuration secrets must never appear in target metadata, experiment records, or evidence.
- Automated scans of stored data enforce `NFR-SEC-02`: zero unredacted secrets in stored data.

## PII Redaction

- Seed PII types (SSN, email, phone, address, names) into prompts, outputs, tool calls, and retrieval content, and assert redaction at ingestion and the redaction rate target from `NFR-SEC-03`.
- Redaction is configurable per organization and per project; tests cover default and configured policies.
- Raw trace access requires explicit authorization and is audit-logged; unauthorized access attempts fail.

## Prompt Injection and Red-Team Evaluation

Red-team evaluation is driven by threat models and known attack classes, not random payloads. It runs in simulation mode with side effects blocked or sandboxed, and never against production by default. Red-team data is restricted to authorized personnel.

The red-team suite maps recognized taxonomies (including the OWASP agentic categories) into executable tests:

- **Tool misuse**: the agent calls the wrong tool, calls tools with fabricated arguments, hallucinates nonexistent tools, or attempts tools it was not given.
- **Identity/privilege abuse**: the agent acts beyond its granted authority or attempts to escalate privilege.
- **Memory poisoning**: persistent agents are tested with poisoned memory that must not corrupt later behavior, leak across users or tenants, or silently persist.
- **Cascading failures**: one agent or tool failure propagating into uncontrolled multi-agent behavior.
- **Human-agent trust exploitation**: high-risk workflows where a human could be manipulated into authorizing destructive actions.
- Prompt injection: direct and indirect injections through inputs, tool results, and retrieved content; output that attempts to exfiltrate instructions.

Excessive agency is mandatory coverage for agents: the model choosing a tool is not authorization to execute it, and tests must prove the failure path is tested before real authority is granted.

## Dependency Supply-Chain Scans

- Dependency manifests are scanned for known-vulnerability advisories; failing or high-severity findings block the PR gate.
- Scan results are pinned to lockfiles so the scanned artifact matches what is installed.
- Evaluator plugins and target adapters are covered by the same supply-chain scanning as first-party code.
- Model and tool provenance is evaluated where applicable, per `grilling.md`: supply-chain risk includes model, tool, and dependency provenance.

## Infrastructure Security Scans

- Container images and infrastructure-as-code are scanned for misconfiguration and known-vulnerability findings.
- Staging and production configurations are scanned for exposed secrets, permissive network rules, and missing security controls.
- Findings are triaged with severity; critical and high findings gate deployment.

## Repository Secret Scanning

- The repository itself is scanned for committed secrets on every push: API keys, tokens, credentials, and private-key material.
- A detected real secret blocks the merge and requires revocation and rotation, never merely deletion of the file.
- Test payloads that intentionally contain secret-like patterns are populated only by seeded, synthetic fixtures, never by real credential material.

## CI Gate

Security tests and scans are enforced by the security CI gate defined in `docs/ci-cd/pull-request-gates.md`. Mandatory per-change coverage includes authentication and authorization tests, tenant isolation tests, secrets handling tests, repository secret scanning, and dependency supply-chain scans. Red-team and infrastructure-scan suites run on schedules in the restricted staging environment, and their results are archived as artifacts.