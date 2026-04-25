"""`shushu delete NAME` — remove a secret."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None):
        raise ShushuError(
            EXIT_USER_ERROR,
            "delete --user not yet implemented",
            "coming in Task 26",
        )
    store.delete(args.name)  # NotFoundError caught by main()
    if args.json:
        emit_result({"name": args.name, "deleted": True}, json_mode=True)
    else:
        print(f"shushu: deleted {args.name}")
    return 0
