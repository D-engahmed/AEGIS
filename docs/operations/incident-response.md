# Incident Response

AEGIS issues reliability and safety verdicts for other AI systems; when AEGIS itself fails, the response material. This document defines severity levels, the on-call structure, the incident lifecycle, and the runbook list for the known failure classes from `docs/architecture/failure-architecture.md`, verified in part by chaos testing (`docs/testing/chaos-testing.md`).

## Severity Levels

| Severity | Definition | Initial response | Examples |
|---|---|---|---|
| **Critical** | Public/tenant harm, data exposure, evidence corruption, or loss of the platform's correctness guarantees | Immediate, continuous engagement until contained | Secret leaked, tenant-isolation breach, evidence corruption, execution duplication, availability loss for a major tenant |
| **Major** | Significant degradation of a core function or infrastructure dependency; the platform may be operating with a violated invariant | Engage on-call immediately; page escalation if not contained within the SLO window | Queue unavailable, database saturation, object storage failure, API latency over threshold, retry storm |
| **Minor** | Degraded experience or a single component impairment that does not threaten correctness or isolation | Fix during on-call hours; no page if contained | Evaluator process failures above baseline, isolated worker failure, provider outage for a non-critical target |
| **Informational** | Non-urgent findings, expected failure-class outcomes, monitoring noise | Log and review at shift handover | Chaos-run findings that confirm expected behavior, transient rate-limit spikes |

Severity can be downgraded after containment and upgraded if scope widens. A "Major" that starts corrupting evidence becomes "Critical."

## On-Call Structure

- **Primary on-call**: the operator responding to pages, following the runbook for the incident class.
- **Escalation**: secondary on-call (or engineering lead) engaged when the primary cannot contain within the response window or when the incident crosses team boundaries.
- **Incident commander**: for Critical incidents, a single commander coordinates response, communication, and handoffs. The commander is not the person deep in the terminal; they own time and decisions.
- **Security response**: any secret-leak, tenant-isolation, or evidence-integrity suspicion invokes the security responder alongside on-call (`secrets-management.md`).
- **Handover**: incidents that outlive a shift are handed over with a running timeline, current containment state, and the next planned action. Nothing is left as "investigate later" without an owner.

## Incident Lifecycle

```text
Detect -> Classify -> Respond -> Mitigate -> Communicate -> Postmortem
```

1. **Detect**: an alert fires (`observability.md`), a user reports an anomaly, or a security scan finds a finding. Detection sources feed the same triage.
2. **Classify**: identify the failure class, assess scope and severity, and open the matching runbook. Classification first, reaction second — the wrong class leads to the wrong mitigation.
3. **Respond**: execute the runbook. Containment outranks completeness: stop the bleeding, then diagnose.
4. **Mitigate**: apply the fix, restore service, and verify the system recovered.
5. **Communicate**: notify affected users via webhooks and the status channel; provide status at agreed intervals until resolved.
6. **Postmortem**: within the documented window, write the postmortem, verify the chaos questions were re-checked, and feed findings back into `failure-architecture.md`, the testing strategy, and the chaos program.

During every incident, re-check the chaos questions as operational invariants (from `chaos-testing.md`):

```text
Did execution duplicate?
Did evidence corrupt?
Did a retry storm happen?
Was the user notified?
Did the system recover?
```

These are not "nice to verify after the fire is out." They are the acceptance test for the response.

## Runbooks for Known Failure Classes

### Queue Unavailable

| Step | Action |
|---|---|
| Confirm | Redis unreachable from API and workers; queue depth metrics flat; jobs stuck `queued` |
| Contain | Do not restart workers blindly (they may hold in-flight jobs). Fail closed or degrade per policy; never silently drop jobs — routing to dead-letter is the audited drop path, silent loss is not |
| Mitigate | Restore Redis (failover/restart per deployment model); confirm queue data intact; allow workers to resume |
| Verify (chaos questions) | No execution duplicated; no evidence corrupted; no retry storm (bounded retries + jitter honored); on-call notified; system recovered and jobs resumed or dead-lettered |

### Worker Crash / Duplication Suspicion

| Step | Action |
|---|---|
| Confirm | Worker terminated mid-job; job redelivered; duplicate execution records or repeated external side effects suspected |
| Contain | Pause or isolate the affected worker; do not discard the job — idempotency is the guard, not deletion |
| Mitigate | Verify the execution ID + idempotency key deduplicated the redelivery (FR-EXE-05); reconcile any duplicate records; preserve partial evidence |
| Verify | **Did execution duplicate?** No. **Did evidence corrupt?** No. Partial evidence preserved and linked to the correct execution |

### Evidence Corruption

| Step | Action |
|---|---|
| Confirm | Evidence-integrity/durability alert; score-to-evidence links broken; checksum mismatch (NFR-DURAB-01) |
| Contain | Quarantine the affected artifact set; stop any reporting or gating that relies on the corrupted evidence — "no score without evidence" fails closed |
| Mitigate | Restore from verified backup (`backup-and-recovery.md`) without overwriting newer immutable data; re-drive affected executions if they were lost, not recovered |
| Verify | Evidence integrity verified after restore (checksums, restore drill results); never present a score whose evidence is missing |

### Retry Storm

| Step | Action |
|---|---|
| Confirm | Burst of synchronized retries across workers after a provider/dependency outage; queue depth spiking; provider rate-limit errors climbing |
| Contain | Do not add unbounded retry capacity. Check retry bounds and backoff configuration; if misconfigured, fix config (which passes review, `configuration.md`) |
| Mitigate | Enforce bounded retries with backoff + jitter; apply per-target concurrent-invocation and retry budgets (FR-EXE-06); let the storm drain |
| Verify | **Did a retry storm happen?** It did; it was controlled. No duplicated side effects, no unbounded retry, cost within budget |

### Database Saturation

| Step | Action |
|---|---|
| Confirm | Connection pool > 80% sustained, blocked connections, replication lag, slow-query rate above baseline (NFR-PERF thresholds) |
| Contain | Identify the hotspot (evaluation write burst, missing index, runaway query). Stop additional load into the store where safe |
| Mitigate | Add pool capacity or scale the store per the scaling strategy (ADR-003 partition/index discipline), fix the query or burst pattern, reduce write amplification |
| Verify | Pool and lag return to baseline; evidence writes were not silently dropped; executions retry within bounds |

### Object Storage Failure

| Step | Action |
|---|---|
| Confirm | Uploads fail mid-write (artifacts, trace payloads, reports); partial artifacts visible |
| Contain | Do not finalize reports or gates from incomplete artifacts; partial artifact must never be treated as complete (chaos gamut) |
| Mitigate | Restore service (failover/replication) per the backup-and-recovery model; re-upload failed or partial artifacts; verify hashes |
| Verify | No evidence corrupted; failed != cancelled; artifacts deduplicated not duplicated; report finalized only after complete artifacts verified |

### Evaluator Process Failure

| Step | Action |
|---|---|
| Confirm | Evaluator plugin process killed mid-scoring; scores half-recorded or absent |
| Contain | Stop the evaluation run from presenting incomplete scores as results; keep the execution in a retryable or partial state |
| Mitigate | Restart the evaluator process; resume scoring retried within bounds; if the evaluator is fundamentally broken, fail the run with a classified failure, not a silent pass |
| Verify | No uncollected scores masquerade as results; failed != cancelled; evidence preserved |

### Target Provider Outage

| Step | Action |
|---|---|
| Confirm | Provider timeouts/500s/rate-limit/malformed responses at scale (chaos "blackout" condition) |
| Contain | Do not hammer the provider; rely on bounded retries with backoff and jitter; apply per-target limits |
| Mitigate | Wait out, or switch authorized fallbacks if configured; never bypass rate limits to "help" |
| Verify | No retry storm; no duplicated side effects; users notified of failed/cancelled executions; system recovered when provider returns |

### Secret Leak

| Step | Action |
|---|---|
| Confirm | Secret-detection alert fired on a model output or trace (FR-TRC-05; Q461) |
| Contain | Escalate security response; treat as Critical; assume the secret is compromised |
| Mitigate | Redact stored material, purge plaintext via audited deletion, rotate and revoke the affected secret (`secrets-management.md`) |
| Verify | Zero unredacted secrets in stored data (NFR-SEC-02); affected scope assessed; affected users notified |

### Tenant-Isolation Suspicion

| Step | Action |
|---|---|
| Confirm | Cross-tenant data access attempt detected (NFR-SEC-01); authorization or RLS bypass suspected |
| Contain | Restrict the affected API/worker/store access path; fail closed on any operation that cannot prove tenant scoping |
| Mitigate | Verify application-level scoping and RLS enforcement; fix the gap; run the tenant-isolation test suite before restoring service |
| Verify | Zero cross-tenant leakage confirmed end-to-end; the isolation property is re-proven, not assumed |

## Communication

- **Affected users**: notified through the notification system — webhooks and alerts per `docs/api/webhooks.md` — when their executions fail, cancel, or when their data may have been exposed. Notification is an invariant: chaos verification includes "Was the user notified?"
- **Status channel**: ongoing status updates at agreed intervals for Major and Critical incidents, including what is affected, what the current containment is, and when the next update lands.
- **Escalation**: the incident commander and security responder are reachable through the documented escalation path; handovers record the timeline.

## Postmortem Requirement

Every Major and Critical incident produces a postmortem that:

1. Records the timeline, the classification, the runbook used, and the chaos-question verdicts.
2. Answers the five chaos questions explicitly for the failure that occurred.
3. Identifies the concrete gap the incident exposed. Findings feed back into, in order: `docs/architecture/failure-architecture.md` (a violated invariant is an architecture finding), `docs/testing/` (a gap that should have been caught becomes a test or a chaos injection), and the CI/CD gates (a gate that did not catch it is tightened).
4. Produces at least one action owned by a named person, with a due date, that closes the gap.

A postmortem that produces no change is not a postmortem; it is a report. The requirement maps to the documentation philosophy that operations verifies reality and feeds back into requirements (`docs/README.md`).

## Related Documentation

- `docs/architecture/failure-architecture.md` — the failure classes and recovery semantics the runbooks implement
- `docs/testing/chaos-testing.md` — the chaos runbook conditions operators practice under
- `docs/operations/observability.md` — alert-to-runbook mapping and the metric thresholds
- `docs/operations/secrets-management.md` — the secret-leak path in detail
- `docs/operations/backup-and-recovery.md` — restore procedures used by the evidence/object-storage runbooks