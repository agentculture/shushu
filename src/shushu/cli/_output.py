"""Output helpers: text vs. JSON modes.

Rules:
- `--json` → ONE JSON object on stdout, nothing else.
- Text mode → concise human output on stdout; warnings go to stderr.
- Errors share the same shape (text vs. JSON) and always include a
  remediation field.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any

from shushu.cli._errors import ShushuError


def emit_result(payload: Any, *, json_mode: bool, stream: IO[str] | None = None) -> None:
    stream = stream or sys.stdout
    if json_mode:
        wrapped: dict[str, Any] = {"ok": True}
        if isinstance(payload, dict):
            wrapped.update(payload)
        elif payload is not None:
            wrapped["result"] = payload
        stream.write(json.dumps(wrapped) + "\n")
    elif payload is None:
        return
    else:
        if isinstance(payload, str):
            stream.write(payload)
            if not payload.endswith("\n"):
                stream.write("\n")
        else:
            stream.write(str(payload) + "\n")


def emit_error(err: ShushuError, *, json_mode: bool, stream: IO[str] | None = None) -> None:
    if stream is None:
        # --json contract: one JSON object on stdout (success OR error), so
        # callers can `payload = json.loads(proc.stdout)` regardless of exit
        # code. Text mode keeps errors on stderr so stdout stays clean.
        stream = sys.stdout if json_mode else sys.stderr
    if json_mode:
        payload = {
            "ok": False,
            "error": {
                "code": err.code,
                "name": err.name,
                "message": err.message,
                "remediation": err.remediation,
            },
        }
        stream.write(json.dumps(payload) + "\n")
    else:
        stream.write(f"shushu: error: {err.message}; {err.remediation}\n")


def emit_warning(message: str, *, json_mode: bool) -> None:
    """Warnings always go to stderr, regardless of json_mode, so agent
    stdout parsing stays clean."""
    if not json_mode:
        sys.stderr.write(f"shushu: warning: {message}\n")
    # In json_mode we suppress warnings entirely (payloads carry their own
    # structured alert info when relevant).
