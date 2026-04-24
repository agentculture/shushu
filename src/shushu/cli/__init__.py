"""shushu CLI entry point.

This package will grow `_build_parser` + `_dispatch` + per-verb modules
under `_commands/` as the spec is implemented. For now it preserves the
scaffold's behaviour so the version test stays green.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from shushu import __version__

PROG = "shushu"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="shushu — agent-first per-OS-user secrets manager",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    parser.parse_args(argv)
    # Scaffold behaviour: no args → print version and exit 0.
    print(f"{PROG} {__version__}")
    return 0


__all__ = ["main"]
