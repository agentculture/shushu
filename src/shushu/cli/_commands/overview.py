"""`shushu overview` — rich metadata snapshot with alert classification."""

from __future__ import annotations

from shushu import alerts, fs, store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            EXIT_USER_ERROR,
            "overview --user / --all-users not yet implemented",
            "coming in Task 26",
        )
    # Read-only: don't trigger store-dir creation if no store exists yet.
    if not fs.user_store_paths().file.exists():
        data = store.StoreData(schema_version=store.SCHEMA_VERSION, secrets=[])
    else:
        data = store.load()
    records = []
    for record in data.secrets:
        state = alerts.classify(record.alert_at)
        if args.expired and state != "expired":
            continue
        records.append(_record_to_dict(record, state))
    if args.json:
        emit_result({"secrets": records}, json_mode=True)
    else:
        _render_text(records)
    return 0


def _record_to_dict(record, state):
    return {
        "name": record.name,
        "hidden": record.hidden,
        "source": record.source,
        "purpose": record.purpose,
        "rotation_howto": record.rotation_howto,
        "alert_at": record.alert_at.isoformat() if record.alert_at else None,
        "alert_state": state,
        "handed_over_by": record.handed_over_by,
        "created_at": record.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": record.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _render_text(records):
    if not records:
        print("(no secrets)")
        return
    for record in records:
        flags = []
        if record["hidden"]:
            flags.append("hidden")
        if record["alert_state"] != "ok":
            flags.append(record["alert_state"])
        tag = f"  [{','.join(flags)}]" if flags else ""
        name, source, purpose = record["name"], record["source"], record["purpose"]
        print(f"{name}{tag}  source={source}  purpose={purpose!r}")
