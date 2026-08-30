# Load Testing

## Purpose

Load testing verifies that AEGIS behaves correctly under normal and anticipated-peak load, and collects the data used for capacity planning. It is distinct from stress testing: stress testing pushes past designed limits to find the breaking point and prove failure containment; load testing operates within the designed envelope and proves the system meets its performance targets there.

Load testing answers:

- How many requests per second can the API sustain at the required latency?
- What are p50, p95, and p99 latency under expected load?
- What does a run cost when an experiment executes at anticipated concurrency?
- Does the system stay stable over extended operation (soak)?
- How does the system behave as load ramps up versus hits instantly?

## Scope

- **Normal load**: the steady-state traffic pattern expected from the product's usage.
- **Anticipated-peak load**: the highest load AEGIS expects to see in a scheduling window or product surge, with headroom.
- **Latency percentiles**: p50, p95, and p99 for API operations and for experiment execution, measured per the notes in `docs/requirements/non-functional-requirements.md`.
- **Cost per run**: target-invocation cost separated from evaluator cost, tracked so evaluation cost surprises surface before budgeting.
- **Soak**: sustained load over time to find leaks, slow degradation, queue drift, and memory growth that short runs miss.
- **Ramp-up patterns**: stepped and gradual ramp-ups to observe whether the scheduler, queue, and workers adapt to growing load or only to load present at start.

Soak testing is the load-testing counterpart to chaos testing: chaos proves failure handling, soak proves that nothing slowly decays during hours of correct operation.

## Load Test Plan

| Scenario | Expected Load | Latency Targets | Limits | Exit Criteria |
|---|---|---|---|---|
| API steady state | Anticipated-peak RPS for reads and creates across tenants | p50 within budget, p95 < NFR-PERF-01, p99 within budget | Max RPS sustained without breach | All latency targets met for the full window; no error-rate breach |
| Experiment execution concurrency | Peak concurrent runs at representative test-case counts | Run completion latency (queue to terminal state) within target | Max concurrent runs at target latency | Throughput >= NFR-PERF-04 target; no runs stuck in queued or running |
| Trace ingestion | Peak trace volume per NFR-PERF-02 envelope | p95 ingestion latency within budget | Max ingestion rate at budget latency | No drop or unbounded backlog; linkage integrity preserved |
| Result query load | Peak result-set retrieval rate | Query p95 < NFR-PERF-03 | Max result sets at target latency | Slow-query count within threshold |
| Evaluator pool load | Peak evaluator RPC volume at anticipated concurrency | Evaluator boundary latency within budget | Max concurrent evaluations | Evaluator queue drains; no evidence loss |
| Soak (stability) | Steady anticipated-peak load for several hours | p95 stable across the window | No monotonic degradation | Latency and error rate flat at end of window; memory and queue depth bounded |
| Ramp-up | Stepped load from 10% to 120% of anticipated peak | Targets hold at each step | Peak step sustained | Healthy adaptation at each step; recovery after each step |

Every scenario records the environment (production-equivalent staging), the load profile, the measurements, and the pass or fail verdict, matching the NFR eight-attribute template used in `docs/requirements/non-functional-requirements.md`.

## Relation to NFR-PERF-01

`NFR-PERF-01` (API p95 latency below 500ms measured from gateway to response completion) is the primary latency budget that the API scenarios verify. Any load test that exercises the API records against it. The related throughput and ingestion NFRs define the corresponding ceilings:

- `NFR-PERF-01` — API p95 latency.
- `NFR-PERF-02` — trace ingestion p95 latency.
- `NFR-PERF-03` — evaluation result query p95 latency.
- `NFR-PERF-04` — experiment execution throughput.

## Outputs

- A load test report per run: scenario, load profile, percentiles, throughput, cost per run, error rates, and environment.
- Capacity planning data: the RPS and concurrency ceilings measured in each scenario, archived so sizing decisions reference measured numbers.
- Archived artifacts, since results are the evidence for capacity claims.

## Scheduling

Load tests are tagged `expensive` and scheduled on the cadence defined in the CI/CD gates. Soak runs are the most expensive and run on their own schedule. Results are archived; never rebuild capacity conclusions from memory.