"""`shushu generate NAME [flags]` — random secret."""

from __future__ import annotations

from dataclasses import dataclass

from shushu import alerts
from shushu import generate as gen
from shushu import privilege, store
from shushu.cli._commands._write_helper import write_value
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


@dataclass(frozen=True)
class _AdminGenerateSnapshot:
    """Plain-value snapshot of args for the admin fork-child closure."""

    name: str
    nbytes: int
    encoding: str
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
    _check_admin_source_prefix(args.source)
    alert_at = _parse_alert_at(args)
    value = _random_value(args)
    rec = write_value(args, value, alert_at)
    _emit(rec, args)
    return 0


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    handed_over_by = privilege.sudo_invoker()
    snap = _AdminGenerateSnapshot(
        name=args.name,
        nbytes=args.nbytes,
        encoding=args.encoding,
        purpose=args.purpose,
        rotate_howto=args.rotate_howto,
        alert_at=args.alert_at,
        hidden=args.hidden,
        json_mode=args.json,
        source=args.source or f"admin:{handed_over_by}",
        handed_over_by=handed_over_by,
    )

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        alert_at_c = _parse_alert_at_raw(snap.alert_at)
        value = _random_value_raw(snap.nbytes, snap.encoding)
        rec = _admin_create_or_overwrite(snap, value, alert_at_c)
        _emit_admin(rec, snap)
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)


def _parse_alert_at_raw(raw):
    try:
        return alerts.parse_date(raw)
    except ValueError as exc:
        raise ShushuError(EXIT_USER_ERROR, f"invalid date: {raw!r}", "use YYYY-MM-DD") from exc


def _random_value_raw(nbytes, encoding):
    try:
        return gen.random_secret(nbytes=nbytes, encoding=encoding)
    except ValueError as exc:
        raise ShushuError(
            EXIT_USER_ERROR, str(exc), "use positive --bytes and --encoding hex|base64"
        ) from exc


def _admin_create_or_overwrite(snap, value, alert_at_c):
    """Create or regenerate under target uid (admin path).

    Mirrors set's overwrite-immutability semantics: preserve hidden /
    source / handed_over_by from the existing record on overwrite.
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


def _emit_admin(rec, snap):
    """Admin-path emit: hidden suppresses value in both JSON and text."""
    if snap.json_mode:
        payload = {
            "name": rec.name,
            "hidden": rec.hidden,
            "encoding": snap.encoding,
            "bytes": snap.nbytes,
        }
        if not rec.hidden:
            payload["value"] = rec.value
        emit_result(payload, json_mode=True)
        return
    if rec.hidden:
        print(f"shushu: generated {rec.name} (hidden, {snap.nbytes} bytes {snap.encoding})")
    else:
        print(f"shushu: generated {rec.name} ({snap.nbytes} bytes {snap.encoding})")
        print(rec.value)


def _check_admin_source_prefix(source) -> None:
    if source and source.startswith("admin:"):
        raise ShushuError(
            EXIT_USER_ERROR,
            f"source {source!r} is reserved for sudo handoff",
            "drop the --source flag",
        )


def _parse_alert_at(args):
    try:
        return alerts.parse_date(args.alert_at)
    except ValueError as exc:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"invalid date: {args.alert_at!r}",
            "use YYYY-MM-DD",
        ) from exc


def _random_value(args) -> str:
    try:
        return gen.random_secret(nbytes=args.nbytes, encoding=args.encoding)
    except ValueError as exc:
        raise ShushuError(
            EXIT_USER_ERROR,
            str(exc),
            "use positive --bytes and --encoding hex|base64",
        ) from exc


def _emit(rec, args) -> None:
    if args.json:
        payload = {
            "name": rec.name,
            "hidden": rec.hidden,
            "encoding": args.encoding,
            "bytes": args.nbytes,
        }
        if not rec.hidden:
            payload["value"] = rec.value
        emit_result(payload, json_mode=True)
        return
    if rec.hidden:
        print(f"shushu: generated {rec.name} (hidden, {args.nbytes} bytes {args.encoding})")
    else:
        print(f"shushu: generated {rec.name} ({args.nbytes} bytes {args.encoding})")
        print(rec.value)
