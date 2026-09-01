"""AEGIS command-line interface.

Provides the minimal production entrypoints until the interface layer ships
real service endpoints: `version` prints the installed release and `probe`
verifies the runtime is healthy (imports resolve, version is readable).
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


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="aegis", description=aegis.__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="print the aegis version")
    p_version.set_defaults(func=_version)

    p_probe = sub.add_parser("probe", help="probe the runtime for health")
    p_probe.set_defaults(func=_probe)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
