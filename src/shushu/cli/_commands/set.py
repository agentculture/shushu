"""`shushu set NAME [value] [flags]`.

With value: create or update (value + metadata).
Without value: update mutable metadata only.
"""

from __future__ import annotations

import sys

from shushu import alerts, privilege, store
from shushu.cli._commands._write_helper import write_value
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        return _handle_admin_user(args)
    alert_at = _parse_alert_at(args)
    _check_admin_source_prefix(args.source)
    if args.value is not None:
        rec = _set_with_value(args, _read_value(args.value), alert_at)
    else:
        rec = _set_metadata_only(args, alert_at)
    _emit_ok(rec, args.json)
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    handed_over_by = privilege.sudo_invoker()
    source = args.source or f"admin:{handed_over_by}"
    # Snapshot all arg values needed inside the child closure.
    arg_name = args.name
    arg_value = args.value
    arg_purpose = args.purpose
    arg_rotate_howto = args.rotate_howto
    arg_alert_at = args.alert_at
    arg_hidden = args.hidden
    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        try:
            alert_at_c = alerts.parse_date(arg_alert_at)
        except ValueError as exc:
            raise ShushuError(
                EXIT_USER_ERROR,
                f"invalid date: {arg_alert_at!r}",
                "use YYYY-MM-DD",
            ) from exc
        if arg_value is None:
            rec = store.update_metadata(
                name=arg_name,
                purpose=arg_purpose,
                rotation_howto=arg_rotate_howto,
                alert_at=alert_at_c,
            )
        else:
            value_c = _read_value(arg_value)
            try:
                existing = store.get_record(arg_name)
            except store.NotFoundError:
                existing = None
            if existing is not None:
                rec = store.set_secret(
                    name=arg_name,
                    value=value_c,
                    hidden=existing.hidden,
                    source=existing.source,
                    purpose=arg_purpose or existing.purpose,
                    rotation_howto=arg_rotate_howto or existing.rotation_howto,
                    alert_at=alert_at_c if alert_at_c is not None else existing.alert_at,
                    handed_over_by=existing.handed_over_by,
                )
            else:
                rec = store.set_secret(
                    name=arg_name,
                    value=value_c,
                    hidden=arg_hidden,
                    source=source,
                    purpose=arg_purpose or "",
                    rotation_howto=arg_rotate_howto or "",
                    alert_at=alert_at_c,
                    handed_over_by=handed_over_by,
                )
        _emit_ok(rec, json_mode)
        return 0

    return admin.as_user(args.user, _child)


def _parse_alert_at(args):
    try:
        return alerts.parse_date(args.alert_at)
    except ValueError as exc:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"invalid ISO date: {args.alert_at!r}",
            "use YYYY-MM-DD (e.g. 2026-10-01)",
        ) from exc


def _check_admin_source_prefix(source) -> None:
    if source and source.startswith("admin:"):
        raise ShushuError(
            EXIT_USER_ERROR,
            f"source {source!r} is reserved for sudo handoff",
            "drop the --source flag (shushu will default to 'localhost')",
        )


def _read_value(v: str) -> str:
    if v == "-":
        # Strip at most ONE trailing newline (the shell-piped sentinel).
        # Preserve any other trailing newlines that are part of the secret.
        return sys.stdin.read().removesuffix("\n")
    return v


def _set_with_value(args, value: str, alert_at):
    return write_value(args, value, alert_at)


def _set_metadata_only(args, alert_at):
    return store.update_metadata(
        name=args.name,
        purpose=args.purpose,
        rotation_howto=args.rotate_howto,
        alert_at=alert_at,
    )


def _rebuild_admin_tail(args) -> str:
    parts = ["set", "--user", args.user, args.name]
    if args.value is not None:
        parts.append(args.value)
    return " ".join(parts)


def _emit_ok(rec, json_mode: bool) -> None:
    if json_mode:
        emit_result(
            {
                "name": rec.name,
                "hidden": rec.hidden,
                "updated_at": rec.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            json_mode=True,
        )
    else:
        print(f"shushu: set {rec.name}")
