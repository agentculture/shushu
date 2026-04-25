"""`shushu generate NAME [flags]` — random secret."""

from __future__ import annotations

from shushu import alerts
from shushu import generate as gen
from shushu import privilege, store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    _check_admin(args)
    _check_admin_source_prefix(args.source)
    alert_at = _parse_alert_at(args)
    value = _random_value(args)
    rec = _persist(args, value, alert_at)
    _emit(rec, args)
    return 0


def _persist(args, value: str, alert_at):
    """Create or regenerate. On regenerate: preserve hidden/source/handed_over_by;
    reject attempts to change immutables (mirrors `set`'s overwrite path)."""
    try:
        existing = store.get_record(args.name)
    except store.NotFoundError:
        existing = None
    if existing is not None:
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


def _check_admin(args) -> None:
    if args.user is None:
        return
    privilege.require_root(f"generate --user {args.user} {args.name}")
    raise ShushuError(
        EXIT_USER_ERROR,
        "generate --user not yet implemented",
        "coming in Task 26",
    )


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
