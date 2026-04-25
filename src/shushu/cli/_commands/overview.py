"""`shushu overview` — rich metadata snapshot with alert classification."""

from __future__ import annotations

from shushu import alerts, fs, store
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "all_users", False):
        return _handle_all_users(args)
    if getattr(args, "user", None):
        return _handle_admin_user(args)
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


def _handle_all_users(args) -> int:
    import json as _json
    import sys as _sys

    from shushu import admin

    expired_only = getattr(args, "expired", False)

    def _row(info):
        paths = admin.store_paths_for(info)
        try:
            data_raw = paths.file.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            raw = _json.loads(data_raw)
            secrets_iter = list(raw.get("secrets", []))
            records = _build_overview_records(secrets_iter, expired_only)
        except (_json.JSONDecodeError, TypeError, KeyError) as exc:
            _sys.stderr.write(f"shushu: warning: skipping {info.name}: corrupt store ({exc})\n")
            return None
        return {"user": info.name, "secrets": records}

    rows = admin.for_each_user(_row)
    if args.json:
        emit_result({"ok": True, "users": rows}, json_mode=True)
    else:
        for row in rows:
            print(f"# {row['user']}")
            _render_text(row["secrets"])
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    expired_only = getattr(args, "expired", False)
    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        if not fs.user_store_paths().file.exists():
            data = store.StoreData(schema_version=store.SCHEMA_VERSION, secrets=[])
        else:
            data = store.load()
        records = []
        for record in data.secrets:
            state = alerts.classify(record.alert_at)
            if expired_only and state != "expired":
                continue
            records.append(_record_to_dict(record, state))
        if json_mode:
            emit_result({"secrets": records}, json_mode=True)
        else:
            _render_text(records)
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)


def _build_overview_records(secrets_iter, expired_only):
    """Build overview rows from a list of raw secret dicts (--all-users path)."""
    from datetime import date as _date

    out = []
    for secret in secrets_iter:
        alert_at_val = None
        if secret.get("alert_at"):
            try:
                alert_at_val = _date.fromisoformat(secret["alert_at"])
            except (ValueError, TypeError):
                pass
        state = alerts.classify(alert_at_val)
        if expired_only and state != "expired":
            continue
        out.append(
            {
                "name": secret["name"],
                "hidden": secret.get("hidden", False),
                "source": secret.get("source", ""),
                "purpose": secret.get("purpose", ""),
                "rotation_howto": secret.get("rotation_howto", ""),
                "alert_at": secret.get("alert_at"),
                "alert_state": state,
                "handed_over_by": secret.get("handed_over_by"),
                "created_at": secret.get("created_at"),
                "updated_at": secret.get("updated_at"),
            }
        )
    return out


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
