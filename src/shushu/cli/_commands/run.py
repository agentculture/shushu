"""`shushu run --inject VAR=NAME ... -- cmd [args]` — exec with env."""

from __future__ import annotations

import os

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError


def handle(args) -> int:
    cmd = _resolve_cmd(args.cmd_and_args or [])
    env_add = _build_env(args.inject)
    new_env = {**os.environ, **env_add}
    try:
        os.execvpe(cmd[0], cmd, new_env)  # nosec B606 — input from CLI  # noqa: S606
    except FileNotFoundError as exc:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"command not found: {cmd[0]!r}",
            "check PATH or use an absolute path",
        ) from exc
    return 0  # unreachable — execvpe replaces the process


def _resolve_cmd(cmd_and_args):
    if not cmd_and_args:
        raise ShushuError(
            EXIT_USER_ERROR,
            "no command given after --",
            "expected form: shushu run --inject VAR=NAME -- <cmd> [args...]",
        )
    # argparse.REMAINDER leaves the leading '--' in the list.
    if cmd_and_args[0] == "--":
        cmd_and_args = cmd_and_args[1:]
    if not cmd_and_args:
        raise ShushuError(
            EXIT_USER_ERROR,
            "no command given after --",
            "expected form: shushu run --inject VAR=NAME -- <cmd>",
        )
    return cmd_and_args


def _build_env(inject_specs):
    env_add: dict[str, str] = {}
    for spec in inject_specs:
        var, name = _parse_inject(spec)
        rec = store.get_record(name)  # NotFoundError caught by main()
        env_add[var] = rec.value  # last-wins on duplicate var
    return env_add


def _parse_inject(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: missing '='",
            "expected form: VAR=NAME (e.g. --inject OPENAI_API_KEY=OPENAI_API_KEY)",
        )
    var, _, name = spec.partition("=")
    if not var:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: empty variable name",
            "expected form: VAR=NAME",
        )
    if not name:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: empty secret name",
            "expected form: VAR=NAME",
        )
    return var, name
