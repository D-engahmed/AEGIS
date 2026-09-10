"""Command-line interface (layer 03 interface surface).

The one CLI: `version` prints the installed release, `probe` verifies the
runtime, `evaluate` runs a deterministic evaluation end-to-end, and `worker`
drains the queue whose adapters are selected by `AEGIS_DATABASE_URL` /
`AEGIS_REDIS_URL`. The container entrypoint (`docker/entrypoint.sh`) and the
pip console script both land here.

Evaluate flow: load a dataset file, register the target + snapshot, build a
REST target client from the target config, and drive the engine through the
worker, then print the run summary, metric results, and persisted evidence
records. This is a thin consumer of the container; all behavior lives behind
`Container.runner` so the command stays free of business logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence

import aegis
from aegis.domain.datasets import (
    add_test_case,
    create_dataset,
    create_dataset_version,
    lock_dataset_version,
)
from aegis.domain.experiments import ExperimentSnapshot, create_experiment
from aegis.domain.targets import (
    TargetType,
    create_target,
    create_target_version,
)
from aegis.infrastructure.rest_target import RestTargetClient
from aegis.interface.container import Container
from aegis.policy.application import Gate, ThresholdGate
from aegis.policy.models import GateSeverity


def _load_dataset(cli: Container, source: str, label: str):
    with open(source, encoding="utf-8") as handle:
        raw = json.load(handle)
    dataset = create_dataset(cli.clock, "org:1", "prj:1", raw.get("name", "cli-dataset"))
    version, _ = create_dataset_version(cli.clock, dataset, label)
    for case in raw.get("test_cases", []):
        version, _ = add_test_case(
            cli.clock,
            version,
            input=case.get("input"),
            expected=case.get("expected"),
            metadata=case.get("metadata", {}),
        )
    locked, _ = lock_dataset_version(cli.clock, version)
    cli.catalog.register_dataset(locked)
    return locked


def _load_target(cli: Container, target_spec: dict, label: str, commit_sha: str | None):
    target = create_target(
        cli.clock,
        "org:1",
        "prj:1",
        target_spec.get("name", "cli-target"),
        TargetType(target_spec.get("target_type", "llm_application")),
    )
    version = create_target_version(
        cli.clock,
        target,
        label,
        config=target_spec.get("config", {}),
        commit_sha=commit_sha,
    )
    cli.catalog.register_target(version)
    return version


def _rest_client(target_version) -> RestTargetClient:
    config = dict(target_version.config)
    base_url = str(config.pop("base_url", "http://127.0.0.1:8080"))
    invoke_path = str(config.pop("invoke_path", "/invoke"))
    headers = dict(config.pop("headers", {}) or {})
    return RestTargetClient(base_url, invoke_path=invoke_path, headers=headers)


def _load_gates(source: str) -> tuple[Gate, ...]:
    """Parse a gate spec: a JSON file path or an inline JSON document.

    Each entry is a threshold gate::

        [
          {"gate_id": "dim/exact-match", "metric": "exact_match", "min_value": 0.9},
          {"metric": "latency_ms", "max_value": 50.0, "severity": "critical"}
        ]

    ``gate_id`` defaults to ``dim/<metric>``; bounds default to no bound except
    the one supplied; ``severity`` is one of ``info/low/medium/high/critical``.
    """
    raw = source
    if os.path.isfile(source):
        with open(source, encoding="utf-8") as handle:
            raw = handle.read()
    spec = json.loads(raw)
    if not isinstance(spec, list):
        raise ValueError("gate spec must be a JSON list of gates")
    gates: list[Gate] = []
    for item in spec:
        if not isinstance(item, dict):
            raise ValueError("each gate must be a JSON object")
        metric = item.get("metric")
        if not metric:
            raise ValueError("each gate requires a `metric`")
        gate_id = item.get("gate_id", f"dim/{metric}")
        severity = GateSeverity(str(item["severity"])) if item.get("severity") else None
        gates.append(
            ThresholdGate(
                gate_id,
                str(metric),
                min_value=item.get("min_value"),
                max_value=item.get("max_value"),
                severity=severity or GateSeverity.HIGH,
            )
        )
    return tuple(gates)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description="AEGIS CLI: run deterministic evaluations end-to-end.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Print the installed release.")
    p_version.set_defaults(func=_cmd_version)

    p_probe = sub.add_parser("probe", help="Probe the runtime for health.")
    p_probe.set_defaults(func=_cmd_probe)

    run = sub.add_parser("evaluate", help="Run a dataset against a REST target.")
    run.add_argument("dataset", help="Path to a JSON dataset file.")
    run.add_argument("--target", help="Target spec JSON file (or use --base-url).")
    run.add_argument("--base-url", help="Target base URL, e.g. http://localhost:8080.")
    run.add_argument("--invoke-path", default="/invoke", help="Target invoke path.")
    run.add_argument("--target-type", default="llm_application")
    run.add_argument("--target-version", default="1.0.0")
    run.add_argument("--dataset-version", default="1.0.0")
    run.add_argument("--evaluators", default="aegis/deterministic/exact_match")
    run.add_argument("--commit-sha", default=None)
    run.add_argument(
        "--gates",
        default=None,
        help="Threshold gate spec: JSON file path or inline JSON list.",
    )
    run.add_argument("--json", action="store_true", help="Emit JSON output.")
    run.set_defaults(func=_cmd_evaluate)

    worker = sub.add_parser(
        "worker",
        help="Claim and execute queued runs from the AEGIS queue (async worker).",
    )
    worker.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum runs to process; default runs until the queue is empty.",
    )
    worker.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling the queue forever (Ctrl-C to stop); for the compose worker.",
    )
    worker.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Idle poll interval in seconds when --watch is set.",
    )
    worker.add_argument("--json", action="store_true", help="Emit JSON output.")
    worker.set_defaults(func=_cmd_worker)
    return parser


def _cmd_version(_args) -> int:
    print(aegis.__version__)
    return 0


def _database_reachable(url: str) -> None:
    """Raise if the configured PostgreSQL endpoint does not answer `SELECT 1`."""
    import psycopg

    with psycopg.connect(url, connect_timeout=2) as conn:
        conn.execute("SELECT 1")


def _queue_reachable(url: str) -> None:
    """Raise if the configured Redis endpoint does not answer `PING`."""
    import redis

    redis.from_url(url, socket_connect_timeout=2).ping()


def _cmd_probe(_args) -> int:
    from aegis.evaluation.plugins import list_evaluators

    evaluators = len(list_evaluators())
    problems: list[str] = []
    stores_checked = 0
    if os.environ.get("AEGIS_DATABASE_URL"):
        try:
            _database_reachable(os.environ["AEGIS_DATABASE_URL"])
            stores_checked += 1
        except Exception as exc:
            problems.append(f"database unreachable: {exc}")
    if os.environ.get("AEGIS_REDIS_URL"):
        try:
            _queue_reachable(os.environ["AEGIS_REDIS_URL"])
            stores_checked += 1
        except Exception as exc:
            problems.append(f"queue unreachable: {exc}")
    if problems:
        print(
            f"aegis {aegis.__version__}: UNHEALTHY ({evaluators} evaluators, "
            f"{stores_checked} stores ok); " + "; ".join(problems)
        )
        return 1
    storage = f", {stores_checked} store(s) reachable" if stores_checked else ""
    print(f"aegis {aegis.__version__}: import ok, {evaluators} evaluators registered{storage}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def drain_queue(container: Container, count: int | None = None) -> int:
    """Run queued jobs to completion; returns how many were processed.

    The queue is at-least-once: a crashed worker abandons its job, and replay
    is safe because run execution is idempotent and evidence linking is
    deduplicated per metric result. Terminal runs are skipped on redelivery.
    """
    handled = 0
    while True:
        job_id = container.queue.claim()
        if job_id is None:
            break
        try:
            run = container.runs.load(job_id)
            if not run.status.terminal:
                target_version = container.catalog.load_target_version(
                    run.snapshot.target_version_id
                )
                engine = container.runner.engine(_rest_client(target_version))
                engine.run(job_id)
            container.runner.finish_run(job_id)
        except Exception:
            container.queue.abandon(job_id)
            raise
        container.queue.complete(job_id)
        handled += 1
        if count is not None and handled >= count:
            break
    return handled


def run_worker(
    cli: Container,
    count: int | None = None,
    watch: bool = False,
    poll_seconds: float = 2.0,
    json_out: bool = False,
) -> int:
    """Drain the queue, optionally polling forever (Ctrl-C stops cleanly)."""
    while True:
        try:
            handled = drain_queue(cli, count=count)
            if json_out:
                print(json.dumps({"processed": handled, "pending": cli.queue.pending()}))
            else:
                print(f"processed {handled} run(s); {cli.queue.pending()} pending")
            if not watch:
                return 0
            time.sleep(poll_seconds)
        except KeyboardInterrupt:
            return 0


def _cmd_worker(args) -> int:
    cli = Container.from_env()
    return run_worker(
        cli,
        count=args.count,
        watch=args.watch,
        poll_seconds=args.poll_seconds,
        json_out=args.json,
    )


def _cmd_evaluate(args) -> int:
    gates = _load_gates(args.gates) if args.gates else ()
    cli = Container.from_env(gates=gates)
    dataset = _load_dataset(cli, args.dataset, args.dataset_version)

    if args.target:
        with open(args.target, encoding="utf-8") as handle:
            spec = json.load(handle)
    else:
        spec = {
            "name": "cli-target",
            "target_type": args.target_type,
            "config": {
                "base_url": args.base_url or "http://127.0.0.1:8080",
                "invoke_path": args.invoke_path,
            },
        }
    target_version = _load_target(cli, spec, args.target_version, args.commit_sha)

    snapshot = ExperimentSnapshot(
        target_version_id=target_version.id,
        dataset_version_id=dataset.id,
        evaluator_version_ids=tuple(args.evaluators.split(",")),
        settings={},
    )
    experiment, _ = create_experiment(
        cli.clock,
        "org:1",
        "prj:1",
        "cli-evaluation",
        snapshot=snapshot,
    )

    client = _rest_client(target_version)
    outcome = cli.runner.run(
        client,
        target_version,
        dataset,
        experiment,
        evaluator_version_ids=experiment.snapshot.evaluator_version_ids,
    )

    run = outcome.run
    gate_report = cli.run_gate_store.load(run.id) if cli.run_gate_store.exists(run.id) else None
    if args.json:
        print(json.dumps(_summary_json(outcome, gate_report), indent=2))
    else:
        _print_human(outcome, gate_report)
    return 0 if run.status.value == "succeeded" else 1


def _gate_json(report) -> dict | None:
    if report is None:
        return None
    return {
        "verdict": report.verdict.value,
        "is_blocked": report.is_blocked,
        "overridden_by": report.override.overridden_by if report.override else None,
        "decisions": [
            {
                "gate_id": d.gate_id,
                "verdict": d.verdict.value,
                "severity": d.severity.value,
                "reason": d.reason,
            }
            for d in report.decisions
        ],
    }


def _summary_json(outcome, gate_report=None) -> dict:
    run = outcome.run
    return {
        "run_id": run.id,
        "status": run.status.value,
        "executions": run.evidence_summary.completed_executions if run.evidence_summary else None,
        "results": [
            {
                "test_case_id": r.test_case_id,
                "metric": r.metric_name,
                "score": r.score,
                "evidence": len(r.evidence),
            }
            for r in outcome.results
        ],
        "evidence_count": len(outcome.evidence),
        "gate": _gate_json(gate_report),
    }


def _print_human(outcome, gate_report=None) -> None:
    run = outcome.run
    print(f"run {run.id}: {run.status.value}")
    if run.evidence_summary is not None:
        summary = run.evidence_summary
        print(
            f"  executions: {summary.completed_executions}/{summary.total_executions} "
            f"(evidence refs {summary.evidence_reference_count}, "
            f"partial={summary.partial_preserved})"
        )
    for r in outcome.results:
        print(f"  {r.test_case_id} {r.metric_name} = {r.score}")
    print(f"evidence records persisted: {len(outcome.evidence)}")
    if gate_report is not None:
        verdict = gate_report.verdict.value
        blocked = " (BLOCKED)" if gate_report.is_blocked else ""
        print(f"gate verdict: {verdict}{blocked}")
        for d in gate_report.decisions:
            print(f"  {d.gate_id}: {d.verdict.value} [{d.severity.value}] {d.reason}")
        if gate_report.override is not None:
            print(
                f"  override by {gate_report.override.overridden_by}: {gate_report.override.reason}"
            )


__all__ = ["drain_queue", "main", "run_worker"]


if __name__ == "__main__":
    sys.exit(main())
