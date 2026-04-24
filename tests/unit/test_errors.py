from __future__ import annotations

import io
import json

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
