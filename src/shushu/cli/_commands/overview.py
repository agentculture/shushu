"""`shushu overview` — rich metadata snapshot with alert classification."""

from __future__ import annotations

from shushu import alerts, store
from shushu.cli._errors import ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            66,
            "overview --user / --all-users not yet implemented",
            "coming in Task 26",
        )
    data = store.load()
    records = []
    for r in data.secrets:
        state = alerts.classify(r.alert_at)
        if args.expired and state != "expired":
            continue
        records.append(
            {
                "name": r.name,
                "hidden": r.hidden,
                "source": r.source,
                "purpose": r.purpose,
                "rotation_howto": r.rotation_howto,
                "alert_at": r.alert_at.isoformat() if r.alert_at else None,
                "alert_state": state,
                "handed_over_by": r.handed_over_by,
                "created_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": r.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    if args.json:
        emit_result({"secrets": records}, json_mode=True)
    else:
        if not records:
            print("(no secrets)")
        for r in records:
            flags = []
            if r["hidden"]:
                flags.append("hidden")
            if r["alert_state"] != "ok":
                flags.append(r["alert_state"])
            tag = f"  [{','.join(flags)}]" if flags else ""
            print(f"{r['name']}{tag}  source={r['source']}  purpose={r['purpose']!r}")
    return 0
