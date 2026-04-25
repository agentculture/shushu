"""`shushu generate NAME [flags]` — random secret."""

from __future__ import annotations

from shushu import alerts
from shushu import generate as gen
from shushu import privilege, store
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
    source = args.source or f"admin:{handed_over_by}"
    arg_name = args.name
    arg_nbytes = args.nbytes
    arg_encoding = args.encoding
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
        try:
            value = gen.random_secret(nbytes=arg_nbytes, encoding=arg_encoding)
        except ValueError as exc:
            raise ShushuError(
                EXIT_USER_ERROR,
                str(exc),
                "use positive --bytes and --encoding hex|base64",
            ) from exc
        try:
            existing = store.get_record(arg_name)
        except store.NotFoundError:
            existing = None
        if existing is not None:
            rec = store.set_secret(
                name=arg_name,
                value=value,
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
                value=value,
                hidden=arg_hidden,
                source=source,
                purpose=arg_purpose or "",
                rotation_howto=arg_rotate_howto or "",
                alert_at=alert_at_c,
                handed_over_by=handed_over_by,
            )
        # Emit using same logic as self-mode but suppress value for hidden.
        if json_mode:
            payload = {
                "name": rec.name,
                "hidden": rec.hidden,
                "encoding": arg_encoding,
                "bytes": arg_nbytes,
            }
            if not rec.hidden:
                payload["value"] = rec.value
            emit_result(payload, json_mode=True)
        else:
            if rec.hidden:
                print(f"shushu: generated {rec.name} (hidden, {arg_nbytes} bytes {arg_encoding})")
            else:
                print(f"shushu: generated {rec.name} ({arg_nbytes} bytes {arg_encoding})")
                print(rec.value)
        return 0

    return admin.as_user(args.user, _child)


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
