"""`shushu show NAME` — metadata record (never value)."""

from __future__ import annotations

from shushu import store
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        return _handle_admin_user(args)
    rec = store.get_record(args.name)  # NotFoundError wrapped by main()
    _emit_record(rec, args.json)
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    target_name = args.name
    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        rec = store.get_record(target_name)
        _emit_record(rec, json_mode)
        return 0

    return admin.as_user(args.user, _child)


def _emit_record(rec, json_mode: bool) -> None:
    payload = {
        "name": rec.name,
        "hidden": rec.hidden,
        "source": rec.source,
        "purpose": rec.purpose,
        "rotation_howto": rec.rotation_howto,
        "alert_at": rec.alert_at.isoformat() if rec.alert_at else None,
        "handed_over_by": rec.handed_over_by,
        "created_at": rec.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": rec.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if json_mode:
        emit_result(payload, json_mode=True)
    else:
        for k, v in payload.items():
            print(f"{k}: {v}")
