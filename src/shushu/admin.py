"""Admin-mode helpers: fork-as-target-user for writes, read-as-root for reads.

Used by every CLI command that accepts --user / --all-users. Keeps the
identity-switch logic out of individual command handlers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from shushu import privilege, users
from shushu.cli._errors import EXIT_BACKEND, ShushuError


def as_user(name: str, fn: Callable[[], int]) -> int:
    """Run fn() as the target user via fork + setuid. Returns the child's exit code.

    Sets HOME to the target user's home directory in the child environment
    so that Path.home() resolves correctly after the uid switch. Each fn
    closure is still responsible for popping SHUSHU_HOME before calling
    store.* functions.
    """
    import os as _os

    privilege.require_root(f"--user {name}")
    try:
        info = users.resolve(name)
    except KeyError as exc:
        raise ShushuError(
            EXIT_BACKEND,
            f"no OS user {name!r} on this host",
            "check: getent passwd",
        ) from exc
    if not info.home.exists():
        raise ShushuError(
            EXIT_BACKEND,
            f"user {name!r} has no home directory",
            "create one or pick a different user",
        )

    def _wrapped() -> int:
        _os.environ["HOME"] = str(info.home)
        return fn()

    return privilege.run_as_user(info, _wrapped)


def for_each_user(
    fn: Callable[[users.UserInfo], dict[str, Any] | None],
) -> list[dict[str, Any]]:
    """Enumerate all OS users with a shushu store and invoke fn per-user.

    Reads only — no uid switch (root reads files directly). Skips users
    with no home dir or no secrets.json. The caller must be root.
    """
    privilege.require_root("--all-users")
    out: list[dict[str, Any]] = []
    for info in users.all_users():
        if not info.home.exists():
            continue
        if not (info.home / ".local/share/shushu/secrets.json").exists():
            continue
        row = fn(info)
        if row is not None:
            out.append(row)
    return out


def store_paths_for(info: users.UserInfo):
    """Compute fs.StorePaths as if we were `info` (without forking).

    Used by --all-users readers so root can stat/read each user's
    secrets.json directly.
    """
    from shushu import fs  # local to avoid circular

    base = info.home / ".local/share/shushu"
    return fs.StorePaths(dir=base, file=base / "secrets.json", lock=base / ".lock")
