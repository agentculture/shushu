"""`shushu list` — names only, one per line."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            EXIT_USER_ERROR,
            "list --user / --all-users not yet implemented",
            "coming in Task 26",
        )
    names = store.list_names()
    if args.json:
        emit_result({"names": names}, json_mode=True)
    else:
        for n in names:
            print(n)
    return 0
