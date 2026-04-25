from __future__ import annotations

import io
import json
import sys

from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_error, emit_result


def test_emit_error_text_single_line():
    buf = io.StringIO()
    emit_error(
        ShushuError(EXIT_USER_ERROR, "FOO is hidden", "use `shushu run --inject`"),
        json_mode=False,
        stream=buf,
    )
    line = buf.getvalue()
    assert line.count("\n") == 1
    assert "shushu: error: FOO is hidden" in line
    assert "use `shushu run --inject`" in line


def test_emit_error_json_structured():
    buf = io.StringIO()
    emit_error(
        ShushuError(EXIT_USER_ERROR, "FOO is hidden", "use inject"),
        json_mode=True,
        stream=buf,
    )
    payload = json.loads(buf.getvalue())
    assert payload == {
        "ok": False,
        "error": {
            "code": 64,
            "name": "EXIT_USER_ERROR",
            "message": "FOO is hidden",
            "remediation": "use inject",
        },
    }


def test_emit_result_text_noop_on_none():
    buf = io.StringIO()
    emit_result(None, json_mode=False, stream=buf)
    assert buf.getvalue() == ""


def test_emit_result_json_wraps_payload_in_ok_true():
    buf = io.StringIO()
    emit_result({"name": "FOO"}, json_mode=True, stream=buf)
    payload = json.loads(buf.getvalue())
    assert payload == {"ok": True, "name": "FOO"}


def test_emit_error_json_default_stream_is_stdout(monkeypatch):
    """In --json mode, both success AND error responses go to stdout, so
    callers can `payload = json.loads(proc.stdout)` regardless of exit code."""
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    emit_error(ShushuError(EXIT_USER_ERROR, "oops", "fix it"), json_mode=True)
    assert buf.getvalue()  # non-empty
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is False


def test_emit_error_text_default_stream_is_stderr(monkeypatch):
    """Text mode keeps errors on stderr so stdout stays clean for piping."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out_buf)
    monkeypatch.setattr(sys, "stderr", err_buf)
    emit_error(ShushuError(EXIT_USER_ERROR, "oops", "fix it"), json_mode=False)
    assert out_buf.getvalue() == ""
    assert "shushu: error: oops" in err_buf.getvalue()
