"""`shushu show NAME` — metadata record (never value)."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        raise ShushuError(
            EXIT_USER_ERROR,
            "show --user not yet implemented",
            "coming in Task 26",
        )
    rec = store.get_record(args.name)  # NotFoundError wrapped by main()
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
    if args.json:
        emit_result(payload, json_mode=True)
    else:
        for k, v in payload.items():
            print(f"{k}: {v}")
    return 0
