"""Privilege handling: euid checks, sudo advice, setuid-fork for handoff.

The setuid-fork helper is the ONLY place in shushu that changes uid/gid.
Every admin-write verb routes through `run_as_user` before touching disk.
"""

from __future__ import annotations

import os
import pwd
import shutil
import sys
from collections.abc import Callable

from shushu.users import UserInfo


class PrivilegeError(Exception):
    """Raised when an operation requires root and the process is not root."""

    def __init__(self, message: str, remediation: str) -> None:  # noqa: B042
        # B042 would prefer `super().__init__(message, remediation)` for
        # pickle round-trips, but that makes `str(exc)` a tuple repr and
        # breaks readable error output. PrivilegeError is not pickled
        # anywhere in shushu; we keep str(exc) clean and expose
        # remediation via the attribute.
        super().__init__(message)
        self.message = message
        self.remediation = remediation


def resolve_shushu_path() -> str:
    """Absolute path to the currently-installed shushu executable.

    `uv tool install` places the binary under ~/.local/bin, which is
    typically absent from root's secure_path — so advising `sudo shushu`
    without the resolved path is a common foot-gun. Fall back to `shushu`
    if which() finds nothing (first-install quirk).
    """
    return shutil.which("shushu") or "shushu"


def require_root(command_tail: str) -> None:
    if os.geteuid() == 0:
        return
    path = resolve_shushu_path()
    raise PrivilegeError(
        message="this operation requires root",
        remediation=f"re-run with: sudo {path} {command_tail}",
    )


def sudo_invoker() -> str:
    """Best-guess name of the human who invoked sudo.

    Prefers $SUDO_USER (set by sudo itself). Falls back to the process's
    real uid (which under sudo is the original caller). Guaranteed non-empty.
    """
    name = os.environ.get("SUDO_USER")
    if name:
        return name
    return pwd.getpwuid(os.getuid()).pw_name


def run_as_user(user: UserInfo, fn: Callable[[], int]) -> int:
    """Fork a child, drop to (user.uid, user.gid), call fn(), exit with its return code.

    Must be invoked with geteuid() == 0 in the parent. Returns the child's
    exit status to the parent.
    """
    if os.geteuid() != 0:
        raise PrivilegeError(
            message="run_as_user requires euid=0 in the parent",
            remediation="this is a programming error; admin handlers must call require_root first",
        )
    pid = os.fork()
    if pid == 0:  # child
        _become(user)
        try:
            rc = fn()
        except PrivilegeError as exc:
            sys.stderr.write(f"shushu: error: {exc.message}\n  → {exc.remediation}\n")
            os._exit(66)
        except Exception as exc:  # pragma: no cover
            sys.stderr.write(f"shushu: internal error in admin handoff: {exc!r}\n")
            os._exit(70)
        os._exit(rc)
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return 67  # EXIT_BACKEND — child died abnormally


def _become(user: UserInfo) -> None:
    """Switch identity. Order matters: setgroups → setgid → setuid."""
    os.setgroups([])
    os.setgid(user.gid)
    os.setegid(user.gid)
    os.setuid(user.uid)
    os.seteuid(user.uid)
