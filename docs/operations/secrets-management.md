# Secrets Management

Secrets are the one category of configuration that never lives in the configuration model. The rule from security architecture and the design interrogation is absolute: **secrets never enter evaluation records or traces** (grilling.md Q60, Q461; `security-architecture.md`). This document defines what a secret is, where secrets live, how they are injected, how they are rotated and revoked, how they are scoped with least privilege, how leakage is detected, and what happens when one leaks.

## What Is a Secret

A secret is any credential or key whose disclosure would grant unauthorized access or capability:

- Model/provider API keys and tokens (the primary case: AEGIS invokes target AI systems on behalf of tenants).
- Database credentials for PostgreSQL (and credentials for any auxiliary store the platform manages).
- Redis password and queue protection credentials.
- Object-storage access keys and secret keys (S3-compatible credentials).
- OAuth2 / OpenID Connect client secrets and signing keys.
- Webhook secrets used to sign or authenticate outbound notifications (`docs/api/webhooks.md`).
- Tenant secrets: per-tenant provider keys, signing keys, and notification credentials.
- Any token, connection string, or certificate private key that could impersonate a service or a tenant.

Secrets are distinct from configuration values: a database URL without an embedded password is configuration; the password in that URL is a secret. Provider configuration in target metadata records a **reference** to the secret, never the value (Q60; `security-architecture.md`).

## Where Secrets Live

- Secrets live in a dedicated **secrets provider**: Vault or a cloud KMS/secrets service, as selected in the infrastructure and security layers (`docs/development/layers/04-infrastructure-layer.md`, `docs/development/layers/11-security-layer.md`).
- Secrets never live in environment files committed to git (`local.env`, `.env`, override files), never in code, never in structured logs, never in traces, and never in evaluation records or evidence artifacts.
- Committed configuration and environment templates contain **references** to secrets (for example, a provider reference key or a vault path), never values.
- A service resolves secret references at startup or runtime through the secrets provider client, with caching and rotation support (`04-infrastructure-layer.md`).

## Injection Mechanism

Secrets are injected at deploy or runtime, not baked into images or config files:

1. **Deploy time**: the deployment mechanism (CI/CD) retrieves secrets from the secrets provider and provisions them to the runtime environment — for example as ephemeral credentials, mounted provider variables, or container orchestration secrets — without writing them into committed files.
2. **Runtime**: services read secret references through the secrets provider client. Provider configuration, database credentials, and webhook secrets are resolved by reference in all environments (local development resolves local fixture or empty values, never real tenant secrets).
3. **No secret in the artifact**: built images and packages contain no secret material; secrets are supplied at run time for that environment only.

The secrets provider client must handle provider outages without corrupting behavior: failures to resolve secrets fail startup (fail-fast, `configuration.md`), and cached secrets are refreshed on rotation.

## Rotation and Revocation

- **Schedule**: secrets are rotated on a documented schedule and whenever compromise is suspected. Provider keys, object-store credentials, and database credentials follow the rotation cadence defined by the security layer; anything suspect is rotated immediately, not at the next scheduled window.
- **Dual-key overlap**: rotation uses an overlapping window — the new secret is issued and verified while the old one remains valid, then the old one is revoked. This avoids taking the platform down to change a credential.
- **Revocation**: revoking a secret must not require touching other secrets (each API key and credential is independently revocable, `security-architecture.md`). Revocation takes effect through the secrets provider and the signing/verification paths.
- **Verification after rotation**: after rotating a secret, verify that the affected service authenticates with the new value and that the old value is rejected. Rotation that breaks a dependency is a failed change, not an acceptable interruption.
- **Audit**: rotation and revocation actions are recorded in the append-only audit log with identity and timestamp (`security-architecture.md`).

## Least-Privilege Scoping

Access to secrets is scoped narrowly, never global:

- **Per service**: the API, workers, and ingestion pipelines hold only the secrets their function requires. A worker that only invokes targets holds the target provider key scope, not the database superuser credentials.
- **Per environment**: local, CI sandbox, staging, and production have disjoint secret sets. A staging provider key is never the production provider key.
- **Per tenant where needed**: tenant provider keys and tenant webhook secrets are scoped to their organization/project. API keys are scoped to organization, project, environment, and target where appropriate; **no global API key exists** (Q92; `security-architecture.md`).

Secret references and their access paths are least-privilege by default: a service that does not prove it needs a secret does not get it.

## Detection and Redaction

AEGIS detects secrets even when they are never supposed to be there. The trace ingestion and evaluation pipelines run secret detection (FR-TRC-05):

```text
1. Detect   - scan model outputs, tool results, and trace content for known secret patterns
              (API keys, tokens, connection strings, signing keys)
2. Redact   - replace detected secrets with redaction markers before storage
3. Alert    - notify the security channel and record the event for incident response
```

Detection and redaction happen **before storage** (grilling.md Q458-Q459). PII redaction is applied in the same pipeline (FR-TRC-04). If a model output or trace contains a secret, the response is fixed and immediate: **detect, redact, alert, and treat as a security incident according to policy** (Q461). This is not a review item and not a follow-up task; it is an incident. Verification: NFR-SEC-02 requires **zero unredacted secrets in stored data**, with continuous secret-detection scanning.

## The Incident Path When a Secret Is Leaked

1. **Detect**: through the secret-detection alert, a tenant report, or scanning.
2. **Classify and contain**: escalate to the on-call and security response per `incident-response.md` (secret-leak runbook, SEV target as defined there). Assume the secret is compromised from the moment of suspicion; do not wait for proof.
3. **Redact and remove**: ensure redaction covers the stored material; purge any stored plaintext from traces, logs, or evaluation records through the audited deletion process (`retention-and-deletion.md`). **Never block reconciliation on UI**: redaction first, cleanup second, but both must happen.
4. **Rotate and revoke**: rotate the affected provider key, database credential, signing key, or webhook secret with dual-key overlap; revoke any tenant-scoped keys in the affected scope.
5. **Investigate scope**: determine what the leaked secret could reach (tenant data, provider spend, warehouse stores). Assess whether evaluation evidence or audit logs were exposed.
6. **Notify**: communicate per the incident-communication policy — affected tenants are notified when tenant secrets or their evaluation data may have been exposed.
7. **Postmortem**: feed the finding back into the failure architecture and testing so the leak path is closed or the detection invariant is strengthened (`incident-response.md`).

Do not leak the secret again in the incident record: incident documentation references the secret path, not the value.

## Reference

- `docs/architecture/security-architecture.md` — secrets management, API keys, redaction, and incident treatment
- `docs/development/layers/11-security-layer.md` — secrets responsibilities and failure modes
- `docs/development/layers/04-infrastructure-layer.md` — the secrets provider client
- `docs/requirements/non-functional-requirements.md` — NFR-SEC-02 zero-unredacted-secrets target
- `docs/operations/incident-response.md` — the secret-leak runbook and communication path