"""shushu CLI entry point: parser + dispatch + error routing."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence

from shushu import __version__, privilege, store
from shushu.cli import _output
from shushu.cli._commands import (
    delete,
    doctor,
    env,
    explain,
    generate,
    get,
    learn,
    list_,
    overview,
    run,
)
from shushu.cli._commands import set as set_cmd
from shushu.cli._commands import (
    show,
)
from shushu.cli._errors import (
    EXIT_INTERNAL,
    EXIT_PRIVILEGE,
    EXIT_STATE,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
    ShushuError,
)

PROG = "shushu"

_HANDLERS = {
    "doctor": doctor.handle,
    "overview": overview.handle,
    "learn": learn.handle,
    "explain": explain.handle,
    "set": set_cmd.handle,
    "show": show.handle,
    "get": get.handle,
    "env": env.handle,
    "run": run.handle,
    "generate": generate.handle,
    "list": list_.handle,
    "delete": delete.handle,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=PROG, description="shushu — agent-first secrets manager")
    p.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    # globals
    pdoc = sub.add_parser("doctor", help="Store health / integrity checks")
    pdoc.add_argument("--json", action="store_true")
    _add_admin_flags(pdoc)
    sub.add_parser("learn", help="Agent-authored self-teaching output").add_argument(
        "--json", action="store_true"
    )
    pe = sub.add_parser("explain", help="Explain a command or concept")
    pe.add_argument("topic")

    po = sub.add_parser("overview", help="Rich metadata snapshot")
    po.add_argument("--json", action="store_true")
    po.add_argument("--expired", action="store_true")
    _add_admin_flags(po)

    # secret verbs
    ps = sub.add_parser("set", help="Create or update a secret")
    ps.add_argument("name")
    ps.add_argument("value", nargs="?")
    ps.add_argument("--source")
    ps.add_argument("--purpose")
    ps.add_argument("--rotate-howto", dest="rotate_howto")
    ps.add_argument("--alert-at", dest="alert_at")
    ps.add_argument("--hidden", action="store_true")
    ps.add_argument("--json", action="store_true")
    _add_admin_flags(ps, all_users=False)

    psh = sub.add_parser("show", help="Show metadata (never value)")
    psh.add_argument("name")
    psh.add_argument("--json", action="store_true")
    _add_admin_flags(psh, all_users=False)

    pg = sub.add_parser("get", help="Print value (refuses hidden)")
    pg.add_argument("name")
    pg.add_argument("--json", action="store_true")

    pe2 = sub.add_parser("env", help="Emit shell export lines")
    pe2.add_argument("names", nargs="+")

    pr = sub.add_parser("run", help="Spawn a subprocess with injected secrets")
    pr.add_argument("--inject", action="append", required=True, metavar="VAR=NAME")
    pr.add_argument("cmd_and_args", nargs=argparse.REMAINDER)

    pgn = sub.add_parser("generate", help="Create a random secret")
    pgn.add_argument("name")
    pgn.add_argument("--bytes", dest="nbytes", type=int, default=32)
    pgn.add_argument("--encoding", choices=["hex", "base64"], default="hex")
    pgn.add_argument("--source")
    pgn.add_argument("--purpose")
    pgn.add_argument("--rotate-howto", dest="rotate_howto")
    pgn.add_argument("--alert-at", dest="alert_at")
    pgn.add_argument("--hidden", action="store_true")
    pgn.add_argument("--json", action="store_true")
    _add_admin_flags(pgn, all_users=False)

    pl = sub.add_parser("list", help="Names-only listing")
    pl.add_argument("--json", action="store_true")
    _add_admin_flags(pl)

    pd = sub.add_parser("delete", help="Remove a secret")
    pd.add_argument("name")
    pd.add_argument("--json", action="store_true")
    _add_admin_flags(pd, all_users=False)

    return p


def _add_admin_flags(p: argparse.ArgumentParser, *, all_users: bool = True) -> None:
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--user", metavar="NAME", help="(sudo) operate on another user's store")
    if all_users:
        grp.add_argument(
            "--all-users",
            action="store_true",
            help="(sudo, read-only) operate across all users",
        )


def _dispatch(args: argparse.Namespace) -> int:
    handler = _HANDLERS.get(args.cmd)
    if handler is None:
        _build_parser().print_help()
        return EXIT_SUCCESS
    return handler(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    json_mode = getattr(args, "json", False)
    if args.cmd is None:
        print(f"{PROG} {__version__}")
        return EXIT_SUCCESS
    try:
        return _dispatch(args)
    except ShushuError as exc:
        _output.emit_error(exc, json_mode=json_mode)
        return exc.code
    except store.ValidationError as exc:
        _output.emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu explain set"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.NotFoundError as exc:
        _output.emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu list"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.HiddenError as exc:
        _output.emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu run --inject"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.StateError as exc:
        _output.emit_error(
            ShushuError(
                EXIT_STATE,
                str(exc),
                "check your ~/.local/share/shushu/ for corruption",
            ),
            json_mode=json_mode,
        )
        return EXIT_STATE
    except privilege.PrivilegeError as exc:
        _output.emit_error(
            ShushuError(EXIT_PRIVILEGE, exc.message, exc.remediation),
            json_mode=json_mode,
        )
        return EXIT_PRIVILEGE
    except NotImplementedError as exc:
        _output.emit_error(
            ShushuError(
                EXIT_USER_ERROR,
                f"not implemented: {exc}",
                "coming in a later task",
            ),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except Exception as exc:  # pragma: no cover
        tb = traceback.format_exc()
        _output.emit_error(
            ShushuError(
                EXIT_INTERNAL,
                f"unexpected error: {exc!r}",
                "please file an issue at github.com/agentculture/shushu/issues with the above",
            ),
            json_mode=json_mode,
        )
        sys.stderr.write(tb)
        return EXIT_INTERNAL


__all__ = ["main"]
