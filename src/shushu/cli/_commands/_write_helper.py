"""Shared write-surface logic for `set` and `generate`.

Centralizes the create-or-overwrite path so the immutability semantics
(`source` and `hidden` are fixed post-create) live in exactly one place.
"""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError


def write_value(
    args,
    value: str,
    alert_at,
    *,
    default_source: str = "localhost",
    default_handed_over_by: str | None = None,
):
    """Create-or-overwrite a record with `value`.

    On overwrite: preserve `source`, `hidden`, and `handed_over_by` from the
    existing record; reject any explicit attempt to change them.

    On create: `source` defaults to `args.source or default_source`,
    `hidden` defaults to `args.hidden`, `handed_over_by = default_handed_over_by`.
    The two `default_*` kwargs are how the admin path injects
    `default_source = f"admin:{invoker}"` and `default_handed_over_by = invoker`
    without duplicating the create/overwrite logic.

    Mutable metadata fields (`purpose`, `rotation_howto`, `alert_at`) follow
    the "user-supplied wins; otherwise inherit from existing" rule.
    """
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
        source=args.source or default_source,
        purpose=args.purpose or "",
        rotation_howto=args.rotate_howto or "",
        alert_at=alert_at,
        handed_over_by=default_handed_over_by,
    )
