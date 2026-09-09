"""Command-line evaluation workflow (layer 03 interface surface).

Runs a deterministic evaluation end-to-end in-process: load a dataset file,
register the target + snapshot, build a REST target client from the target
config, and drive the engine through the worker, then print the run summary,
metric results, and persisted evidence records.

This is a thin consumer of the container; all behavior lives behind
`Container.runner` so the command stays free of business logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

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
    worker.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        return _cmd_evaluate(args)
    if args.command == "worker":
        return _cmd_worker(args)
    parser.print_help()
    return 2


def _cmd_worker(args) -> int:
    """Drain the queue: claim, execute, link evidence, complete (at-least-once).

    A crashed worker abandons its job with the engine idempotent per run and
    evidence linking deduplicated per metric result, so redelivery is safe.
    """
    cli = Container.from_env()
    handled = 0
    while True:
        job_id = cli.queue.claim()
        if job_id is None:
            break
        try:
            run = cli.runs.load(job_id)
            if not run.status.terminal:
                target_version = cli.catalog.load_target_version(run.snapshot.target_version_id)
                engine = cli.runner.engine(_rest_client(target_version))
                engine.run(job_id)
            cli.runner.finish_run(job_id)
        except Exception:
            cli.queue.abandon(job_id)
            raise
        cli.queue.complete(job_id)
        handled += 1
        if args.count is not None and handled >= args.count:
            break
    if args.json:
        print(json.dumps({"processed": handled, "pending": cli.queue.pending()}))
    else:
        print(f"processed {handled} run(s); {cli.queue.pending()} pending")
    return 0


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


__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(main())
