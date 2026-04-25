"""`shushu set NAME [value] [flags]`.

With value: create or update (value + metadata).
Without value: update mutable metadata only.
"""

from __future__ import annotations

import sys

from shushu import alerts, privilege, store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    _check_admin(args)
    alert_at = _parse_alert_at(args)
    _check_admin_source_prefix(args.source)
    if args.value is not None:
        rec = _set_with_value(args, _read_value(args.value), alert_at)
    else:
        rec = _set_metadata_only(args, alert_at)
    _emit_ok(rec, args.json)
    return 0


def _check_admin(args) -> None:
    if args.user is None:
        return
    privilege.require_root(_rebuild_admin_tail(args))
    raise ShushuError(
        EXIT_USER_ERROR,
        "set --user not yet implemented",
        "coming in Task 26 (integration task)",
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
    try:
        existing = store.get_record(args.name)
        existed = True
    except store.NotFoundError:
        existing = None
        existed = False

    if existed:
        if args.source is not None and args.source != existing.source:
            raise ShushuError(
                EXIT_USER_ERROR,
                "source is immutable post-create",
                "delete and re-create to change",
            )
        if args.hidden and not existing.hidden:
            raise ShushuError(
                EXIT_USER_ERROR,
                "hidden is immutable post-create",
                "delete and re-create to change",
            )
        return store.set_secret(
            name=args.name,
            value=value,
            hidden=existing.hidden,
            source=existing.source,
            purpose=args.purpose or existing.purpose,
            rotation_howto=args.rotate_howto or existing.rotation_howto,
            alert_at=alert_at if alert_at is not None else existing.alert_at,
            handed_over_by=existing.handed_over_by,
        )
    return store.set_secret(
        name=args.name,
        value=value,
        hidden=args.hidden,
        source=args.source or "localhost",
        purpose=args.purpose or "",
        rotation_howto=args.rotate_howto or "",
        alert_at=alert_at,
        handed_over_by=None,
    )


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
