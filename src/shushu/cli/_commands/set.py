"""`shushu set NAME [value] [flags]`.

With value: create or update (value + metadata).
Without value: update mutable metadata only.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from shushu import alerts, privilege, store
from shushu.cli._commands._write_helper import write_value
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


@dataclass(frozen=True)
class _AdminSetSnapshot:
    """Snapshot of args needed inside the admin fork-child closure.

    Decouples the closure from the argparse Namespace so the child
    holds only plain values (no shared mutable state with the parent).
    """

    name: str
    value: str | None
    purpose: str | None
    rotate_howto: str | None
    alert_at: str | None
    hidden: bool
    json_mode: bool
    source: str
    handed_over_by: str


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
    admin_source = args.source or f"admin:{handed_over_by}"
    # Snapshot all arg values needed inside the child closure.
    snap = _AdminSetSnapshot(
        name=args.name,
        value=args.value,
        purpose=args.purpose,
        rotate_howto=args.rotate_howto,
        alert_at=args.alert_at,
        hidden=args.hidden,
        json_mode=args.json,
        source=admin_source,
        handed_over_by=handed_over_by,
    )

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        alert_at_c = _parse_alert_at_raw(snap.alert_at)
        if snap.value is None:
            rec = store.update_metadata(
                name=snap.name,
                purpose=snap.purpose,
                rotation_howto=snap.rotate_howto,
                alert_at=alert_at_c,
            )
        else:
            rec = _admin_create_or_overwrite(snap, _read_value(snap.value), alert_at_c)
        _emit_ok(rec, snap.json_mode)
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)


def _parse_alert_at_raw(raw):
    try:
        return alerts.parse_date(raw)
    except ValueError as exc:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"invalid date: {raw!r}",
            "use YYYY-MM-DD",
        ) from exc


def _admin_create_or_overwrite(snap, value, alert_at_c):
    """Create or overwrite under target uid (admin path).

    Mirrors `_write_helper.write_value`'s preserve-immutables semantics
    but uses the admin-supplied `source` and `handed_over_by` defaults
    on the create branch.
    """
    try:
        existing = store.get_record(snap.name)
    except store.NotFoundError:
        existing = None
    if existing is not None:
        return store.set_secret(
            name=snap.name,
            value=value,
            hidden=existing.hidden,
            source=existing.source,
            purpose=snap.purpose or existing.purpose,
            rotation_howto=snap.rotate_howto or existing.rotation_howto,
            alert_at=alert_at_c if alert_at_c is not None else existing.alert_at,
            handed_over_by=existing.handed_over_by,
        )
    return store.set_secret(
        name=snap.name,
        value=value,
        hidden=snap.hidden,
        source=snap.source,
        purpose=snap.purpose or "",
        rotation_howto=snap.rotate_howto or "",
        alert_at=alert_at_c,
        handed_over_by=snap.handed_over_by,
    )


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
