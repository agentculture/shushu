"""Translate domain exceptions to ShushuError + exit code.

Used by `cli.main` for top-level error handling AND by `admin.as_user`
to translate exceptions raised inside fork-child closures so they
produce the same structured error output as self-mode rather than
being treated as EXIT_INTERNAL by `privilege.run_as_user`.

Catches `ShushuError`, `store.ValidationError`, `store.NotFoundError`,
`store.HiddenError`, and `store.StateError`. Lets every other exception
bubble — `cli.main` adds its own broader handler (PrivilegeError,
NotImplementedError, generic Exception with traceback). `admin.as_user`
delegates to `privilege.run_as_user`'s generic catch for the unknown.
"""

from __future__ import annotations

from collections.abc import Callable

from shushu import store
from shushu.cli._errors import EXIT_STATE, EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_error


def translate_errors(fn: Callable[[], int], *, json_mode: bool) -> int:
    """Run fn() and translate domain exceptions to ShushuError + exit code."""
    try:
        return fn()
    except ShushuError as exc:
        emit_error(exc, json_mode=json_mode)
        return exc.code
    except store.ValidationError as exc:
        emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu explain set"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.NotFoundError as exc:
        emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu list"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.HiddenError as exc:
        emit_error(
            ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu run --inject"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except store.StateError as exc:
        emit_error(
            ShushuError(
                EXIT_STATE,
                str(exc),
                "check your ~/.local/share/shushu/ for corruption",
            ),
            json_mode=json_mode,
        )
        return EXIT_STATE
