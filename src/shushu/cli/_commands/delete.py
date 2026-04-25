"""`shushu delete NAME` — remove a secret."""

from __future__ import annotations

from shushu import store
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None):
        return _handle_admin_user(args)
    store.delete(args.name)  # NotFoundError caught by main()
    if args.json:
        emit_result({"name": args.name, "deleted": True}, json_mode=True)
    else:
        print(f"shushu: deleted {args.name}")
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    name_to_delete = args.name
    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        store.delete(name_to_delete)
        if json_mode:
            emit_result({"name": name_to_delete, "deleted": True}, json_mode=True)
        else:
            print(f"shushu: deleted {name_to_delete}")
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)
