# Using AEGIS: a user-story field guide

AEGIS evaluates an AI target (your model / API) against gold-labeled test
cases, records evidence for every metric result, and lets you replay real
traffic offline. Everything below runs against the current `main` build.

You do not need any infrastructure to try the CLI. Add `AEGIS_DATABASE_URL`
and `AEGIS_REDIS_URL` only when you want persistent storage and async run
processing (the compose stack sets these for you).

---

## 0. Quick start

```bash
# install (Python 3.12)
pip install -e ".[dev]"

# start the full stack (Postgres + Redis + API + worker) in the background
docker compose up -d --build

# everything healthy?
docker compose ps                 # all four services "healthy"
docker compose exec api aegis-entrypoint probe
#   aegis 0.1.0: import ok, 3 evaluators registered, 2 store(s) reachable
```

Then open:

| What               | Where                                                        |
| ------------------ | ------------------------------------------------------------ |
| Dashboard (UI)     | http://localhost:8000/                                        |
| Swagger            | http://localhost:8000/docs                                    |
| Live API checks    | http://localhost:8000/health/live (add a bearer token)        |

To use the dashboard you need a token. The API mint one via the dev login
(flag it **off for production**):

```bash
AEGIS_DEV_LOGIN=1 docker compose up -d --build api

curl -s http://localhost:8000/security/dev-token
# {"token": "aegis.v1...", "expires_at": "...", "authentication_method": "service_account"}
```

The dashboard logs itself in with that token and shows experiments, runs,
results and evidence. Everything below also works without the UI via the CLI
and REST API.

---

## 1. "As an evaluator, I want to score my model against a labeled dataset"

### 1.1 Write a dataset

JSON file, one `test_case` per input/golden pair:

```bash
cat > dataset.json <<'EOF'
{"name": "my-qa", "test_cases": [
  {"input": "capital of France?", "expected": "Paris"},
  {"input": "2 + 2?",            "expected": "4"}
]}
EOF
```

### 1.2 Point at your target

Your target exposes `POST /invoke` accepting
`{"test_case_id", "target_version_id", "input", "metadata"}` and returning
`{"output", "latency_ms", "cost_usd", "trace_artifact_id", ...}`. Pass it
inline, or as a spec file:

```bash
cat > target.json <<'EOF'
{"name": "my-app", "target_type": "llm_application",
 "config": {"base_url": "http://my-app:8080", "invoke_path": "/invoke"}}
EOF
```

### 1.3 Run

```bash
aegis evaluate dataset.json --target target.json --gates '[{"metric":"exact_match","min_value":0.5}]'
# run run:xxx: succeeded
#   executions: 2/2 (evidence refs 2, partial=false)
#   tc:... exact_match = 1.0
# evidence records persisted: 2
# gate verdict: pass
aegis evaluate dataset.json --target target.json --json     # machine-readable
```

Exit code is `0` on a completed run, `1` on failure. A `block` gate verdict
still completes the run — the run just cannot be shipped past policy.

### 1.4 That's it — what got recorded?

The run is persisted: executions, metric results, and evidence records. Every
result references the evidence that produced it (content-hashed). You can read
them back through the API (section 5 and 6).

---

## 2. "As an ML engineer, I want to repro evaluations offline from real traffic"

Capture **real** target responses once, then evaluate forever without the
target being reachable or OpenAI/your provider billing you again.

```bash
# 1) capture live traffic (against a reachable target)
aegis record dataset.json --base-url http://my-app:8080 \
       --recordings recordings.jsonl --limit 50
# recorded 50 invocation(s) -> recordings.jsonl

# 2) evaluate against the fixture (no network)
cat > replay-target.json <<'EOF'
{"name": "my-app", "config": {"recordings": "recordings.jsonl"}}
EOF
aegis evaluate dataset.json --target replay-target.json
```

Replay keys each request to a recorded response by `test_case_id`, falling
back to whole-input equality (`match_on: auto|test_case_id|input` in the
target config). Recorded failures replay as the same failure. A fixture is a
JSONL file with a version header:

```
{"aegis_record": "aegis-record/v1"}
{"test_case_id": "tc:...", "input": "hello", "output": "hello", "latency_ms": 1.0,
 "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
 "trace_artifact_id": "trace/ctr", "error_code": null, "error_message": null}
```

The worker honors the same `recordings` config, so async runs replay offline
too. A committed real-traffic fixture ships in
`tests/fixtures/recordings/live-echo.jsonl`.

---

## 3. "As an operator, I want the platform serving HTTP"

```bash
# dev/single box
aegis serve --host 0.0.0.0 --port 8000

# production-equivalent (compose): API + worker forever
docker compose up -d --build            # api on :8000, worker polling the queue
```

App surface (Swagger at `/docs`):

| Method | Path                              | Purpose                          |
| ------ | --------------------------------- | -------------------------------- |
| GET    | `/experiments`                    | list experiments (tenant-scoped) |
| POST   | `/experiments`                    | create experiment (snapshot)     |
| GET    | `/experiments/{id}`               | fetch experiment                 |
| POST   | `/experiments/{id}/start`         | lock snapshot, begin         |
| POST   | `/experiments/{id}/clone`         | variant copy                     |
| GET    | `/experiments/{id}/runs`          | runs for an experiment           |
| POST   | `/runs`                           | submit a run (idempotent key ok) |
| GET    | `/runs/{id}`                      | run status + summary             |
| POST   | `/runs/{id}/cancel`               | cooperative cancel               |
| GET    | `/runs/{id}/results`              | metric results for a run         |
| GET    | `/evidence/runs/{id}`             | evidence for a run               |
| GET    | `/evidence/{id}`                  | one evidence record              |
| GET    | `/evidence/provenance/{metric_id}`| trace provenance for a result    |
| GET    | `/analysis/compare`               | variant comparison               |
| GET    | `/analysis/regression`            | regression detection             |
| GET    | `/analysis/trend/{metric_name}`   | metric trend                     |
| GET    | `/analysis/failures`              | failure clustering               |
| POST   | `/security/tokens`                | mint short-lived token           |
| POST   | `/security/pii/redact`            | redact PII from free text        |
| GET    | `/security/audit`                 | append-only audit trail          |
| GET    | `/policy/verdict/{run_id}`        | gate verdict for a run           |
| POST   | `/policy/verdict/{run_id}/override`| human override                 |
| GET    | `/observability/traces/{run_id}`  | execution traces                 |
| GET    | `/observability/cost/{run_id}`    | cost tracking                    |
| GET    | `/health/live`                    | liveness (behind auth)           |

Auth: `Authorization: Bearer <token>`. Anonymous requests get `401`; tampered
tokens get `403`. Tokens are HMAC-signed — `aegis.v1.<payload>.<sig>`.

---

## 4. "As a QA/analyst, I want to see evidence, not just a number"

```bash
# start the UI (with dev login so it can mint its session token)
AEGIS_DEV_LOGIN=1 docker compose up -d --build api
# open http://localhost:8000/
```

The dashboard lists experiments → runs → results → evidence and lets you
submit a run from the UI. Or drive everything by hand with the API:

```bash
TOKEN=$(curl -s http://localhost:8000/security/dev-token | python -c \
        "import sys,json;print(json.load(sys.stdin)['token'])")
AUTH="Authorization: Bearer $TOKEN"

EXPERIMENT_ID=$(curl -s -H "$AUTH" -X POST http://localhost:8000/experiments \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","project_id":"prj:1",
       "snapshot":{"target_version_id":"...","dataset_version_id":"...",
                   "evaluator_version_ids":["aegis/deterministic/exact_match"]}}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -s -H "$AUTH" -X POST http://localhost:8000/experiments/$EXPERIMENT_ID/start
curl -s -H "$AUTH" -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d "{\"experiment_id\":\"$EXPERIMENT_ID\"}"
# then poll GET /runs/{run_id} until "succeeded"/"failed"

curl -s -H "$AUTH" http://localhost:8000/runs/$RUN_ID/results    # scores
curl -s -H "$AUTH" http://localhost:8000/evidence/runs/$RUN_ID   # evidence
curl -s -H "$AUTH" http://localhost:8000/evidence/provenance/$METRIC_RESULT_ID
```

---

## 5. "As an async runner: I want a queue worker draining my runs"

```bash
aegis worker                 # drain until empty, one-shot
aegis worker --count 10      # drain at most 10
aegis worker --watch         # poll forever (compose uses this)
```

The queue is at-least-once: a crashed worker abandons its job, and redelivery
is safe because run execution is idempotent and evidence linking is
deduplicated per metric result. Watch mode survives poisoned jobs — the worker
logs `worker error (job abandoned)` and keeps polling instead of crash-looping.

---

## 6. "As a security reviewer, I want to know who did what"

- **Roles** gate permissions: `owner` ≥ `admin` ≥ `engineer` ≥ `analyst` ≥
  `viewer`. `admin` cannot edit policy; `owner` can.
- **Audit**: every experiment/run action writes an append-only audit entry —
  `GET /security/audit` lists them per tenant.
- **PII**: `POST /security/pii/redact` masks emails/phones/credit-card spans
  from free text before it goes anywhere.
- **Gates**: `GET /policy/verdict/{run_id}` shows the gate decision; an
  authorized engineer/owner can `POST .../override` to un-block a run, which
  is itself audited.

---

## 7. "As the person who pushes to production"

Dockerized deploy exists (`.github/workflows/deploy.yml`), but real deploys
are **manual and not yet run**. On a Linux VPS with the repo secrets set:

1. GitHub repo → Settings → Secrets and variables → Actions:
   `VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_SSH_KEY` (required), `AEGIS_TAG`
   (optional).
2. Actions → "Deploy to VPS" → Run workflow (manual `workflow_dispatch`).

The workflow clones/pulls the repo to `/opt/aegis`,
`docker compose up -d --build`, then waits for the API `probe` to succeed.

---

## Reference

**Dataset** (`dataset.json`):
```json
{"name": "any", "test_cases": [{"input": "…", "expected": "…", "metadata": {}}]}
```

**Target spec** (`target.json`):
```json
{"name": "any", "target_type": "llm_application",
 "config": {"base_url": "http://host:port",
            "invoke_path": "/invoke",
            "headers": {"X-Api-Key": "…"}}}
```
For offline replay, replace the network config with
`{"config": {"recordings": "path.jsonl", "match_on": "auto"}}`.

**Gates** — inline JSON or a file:
```json
[{"gate_id": "qa/exact", "metric": "exact_match", "min_value": 0.9, "severity": "high"},
 {"metric": "latency_ms", "max_value": 50.0}]
```

**Statuses**: experiment `created → running → succeeded | failed | cancelled`;
run `queued → running | retrying | partial → succeeded | failed | cancelled`.

**Environment** (all optional except in prod):
`AEGIS_DATABASE_URL`, `AEGIS_REDIS_URL`, `AEGIS_ENV=production`,
`AEGIS_DEV_LOGIN=1` (dev only), `AEGIS_TAG`.
Unset DB/Redis URLs => in-memory stores (`aegis` works with zero infra).

**CLI**:
```
aegis version | probe | evaluate | record | worker | serve
```

Checklist before you trust a result: run succeeded, every result shows
`evidence` ≥ 1, gate verdict `pass`, and (when you care) the provenance graph
traces each metric to its execution.