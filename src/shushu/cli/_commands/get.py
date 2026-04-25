"""`shushu get NAME` — print value (refuses hidden)."""

from __future__ import annotations

from shushu import store
from shushu.cli._output import emit_result


def handle(args) -> int:
    value = store.get_value(args.name)  # HiddenError/NotFoundError caught by main()
    if args.json:
        emit_result({"name": args.name, "value": value}, json_mode=True)
    else:
        print(value)
    return 0
