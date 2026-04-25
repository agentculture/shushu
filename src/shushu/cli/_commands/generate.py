"""`shushu generate NAME [flags]` — random secret."""

from __future__ import annotations

from shushu import alerts
from shushu import generate as gen
from shushu import privilege
from shushu.cli._commands._write_helper import write_value
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


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
    admin_source = args.source or f"admin:{handed_over_by}"

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        alert_at = _parse_alert_at(args)
        value = _random_value(args)
        rec = write_value(
            args,
            value,
            alert_at,
            default_source=admin_source,
            default_handed_over_by=handed_over_by,
        )
        _emit(rec, args)
        return 0

    return admin.as_user(args.user, _child, json_mode=args.json)


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
