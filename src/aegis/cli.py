"""AEGIS command-line interface.

Production entrypoints for the deployed container: `version` prints the
installed release, `probe` verifies the runtime is healthy, and `worker`
drains the Redis-backed queue (adapters selected by `AEGIS_DATABASE_URL` /
`AEGIS_REDIS_URL`) so the container executes evaluations end to end.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence

import aegis
from aegis.evaluation.plugins import list_evaluators


def _version(_args: Namespace) -> int:
    print(aegis.__version__)
    return 0


def _probe(_args: Namespace) -> int:
    evaluators = len(list_evaluators())
    print(f"aegis {aegis.__version__}: import ok, {evaluators} evaluators registered")
    return 0


def _worker(args: Namespace) -> int:
    from aegis.interface.cli import drain_queue
    from aegis.interface.container import Container

    container = Container.from_env()
    processed = drain_queue(container, count=args.count)
    print(f"processed {processed} run(s); {container.queue.pending()} pending")
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="aegis", description=aegis.__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="print the aegis version")
    p_version.set_defaults(func=_version)

    p_probe = sub.add_parser("probe", help="probe the runtime for health")
    p_probe.set_defaults(func=_probe)

    p_worker = sub.add_parser(
        "worker", help="claim and execute queued runs (AEGIS_DATABASE_URL/AEGIS_REDIS_URL)"
    )
    p_worker.add_argument(
        "--count",
        type=int,
        default=None,
        help="Maximum runs to process; default runs until the queue is empty.",
    )
    p_worker.set_defaults(func=_worker)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
