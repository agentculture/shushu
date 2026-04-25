"""Error discipline: ShushuError + EXIT_* constants.

Every handler raises ShushuError. The dispatcher catches and routes
through _output.emit_error. Unknown exceptions wrap to EXIT_INTERNAL.
"""

from __future__ import annotations

EXIT_SUCCESS = 0
EXIT_USER_ERROR = 64
EXIT_STATE = 65
EXIT_PRIVILEGE = 66
EXIT_BACKEND = 67
EXIT_CONFLICT = 68
EXIT_INTERNAL = 70

_EXIT_NAMES = {
    EXIT_SUCCESS: "EXIT_SUCCESS",
    EXIT_USER_ERROR: "EXIT_USER_ERROR",
    EXIT_STATE: "EXIT_STATE",
    EXIT_PRIVILEGE: "EXIT_PRIVILEGE",
    EXIT_BACKEND: "EXIT_BACKEND",
    EXIT_CONFLICT: "EXIT_CONFLICT",
    EXIT_INTERNAL: "EXIT_INTERNAL",
}


class ShushuError(Exception):
    """Structured error: exit code + human message + remediation."""

    def __init__(self, code: int, message: str, remediation: str) -> None:  # noqa: B042
        # B042 would prefer super().__init__(code, message, remediation) for
        # pickle round-trips, but that makes str(exc) a tuple repr. We
        # pass only message so str(exc) stays readable; code and
        # remediation live as attributes. Same pattern as PrivilegeError
        # in shushu.privilege.
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation

    @property
    def name(self) -> str:
        return _EXIT_NAMES.get(self.code, f"EXIT_{self.code}")
