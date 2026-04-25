"""`shushu env NAME1 [NAME2 ...]` — emit POSIX shell export lines."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError


def handle(args) -> int:
    records = []
    for name in args.names:
        rec = store.get_record(name)  # NotFoundError caught by main()
        if rec.hidden:
            raise ShushuError(
                EXIT_USER_ERROR,
                f"{name} is hidden",
                f"exclude it or use `shushu run --inject {name}={name} -- <cmd>`",
            )
        records.append(rec)
    for rec in records:
        print(f"export {rec.name}='{_posix_quote(rec.value)}'")
    return 0


def _posix_quote(value: str) -> str:
    """POSIX single-quote-safe: replace embedded ' with '\\''."""
    return value.replace("'", "'\\''")
