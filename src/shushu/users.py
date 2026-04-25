"""OS user enumeration and resolution.

Thin wrapper over `pwd` so the rest of shushu speaks one dataclass.
Used by privilege handoff and admin --all-users enumeration.
"""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserInfo:
    name: str
    uid: int
    gid: int
    home: Path


def _from_pwnam(entry: pwd.struct_passwd) -> UserInfo:
    return UserInfo(
        name=entry.pw_name,
        uid=entry.pw_uid,
        gid=entry.pw_gid,
        home=Path(entry.pw_dir),
    )


def current() -> UserInfo:
    return _from_pwnam(pwd.getpwuid(os.geteuid()))


def resolve(name: str) -> UserInfo:
    return _from_pwnam(pwd.getpwnam(name))


def all_users() -> list[UserInfo]:
    return [_from_pwnam(e) for e in pwd.getpwall()]
