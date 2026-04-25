"""`shushu list` — names only, one per line."""

from __future__ import annotations

from shushu import store
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "all_users", False):
        return _handle_all_users(args)
    if getattr(args, "user", None):
        return _handle_admin_user(args)
    names = store.list_names()
    if args.json:
        emit_result({"names": names}, json_mode=True)
    else:
        for n in names:
            print(n)
    return 0


def _handle_all_users(args) -> int:
    import json as _json
    import sys as _sys

    from shushu import admin

    def _row(info):
        paths = admin.store_paths_for(info)
        try:
            data_raw = paths.file.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            raw = _json.loads(data_raw)
            names = sorted(s["name"] for s in raw.get("secrets", []))
        except (_json.JSONDecodeError, TypeError, KeyError) as exc:
            _sys.stderr.write(f"shushu: warning: skipping {info.name}: corrupt store ({exc})\n")
            return None
        return {"user": info.name, "names": names}

    rows = admin.for_each_user(_row)
    if args.json:
        emit_result({"users": rows}, json_mode=True)
    else:
        for row in rows:
            print(f"# {row['user']}")
            for n in row["names"]:
                print(n)
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        names = store.list_names()
        if json_mode:
            emit_result({"names": names}, json_mode=True)
        else:
            for n in names:
                print(n)
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)
