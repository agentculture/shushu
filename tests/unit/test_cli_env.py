from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stderr, redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_env_emits_single_quoted_exports():
    store.set_secret(name="FOO", value="hello", hidden=False, source="localhost", purpose="")
    store.set_secret(name="BAR", value="world", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["env", "FOO", "BAR"])
    assert rc == 0
    assert "export FOO='hello'" in out
    assert "export BAR='world'" in out


def test_env_escapes_single_quotes_posix_safe():
    store.set_secret(
        name="TRICKY",
        value="it's \"quoted\" and 'risky'",
        hidden=False,
        source="localhost",
        purpose="",
    )
    rc, out, _ = _run(["env", "TRICKY"])
    assert rc == 0
    # Round-trip through bash.
    result = subprocess.run(
        ["bash", "-c", f'{out.strip()}; printf %s "$TRICKY"'],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "it's \"quoted\" and 'risky'"


def test_env_refuses_when_any_name_is_hidden():
    store.set_secret(name="VIS", value="v", hidden=False, source="localhost", purpose="")
    store.set_secret(name="HID", value="h", hidden=True, source="localhost", purpose="")
    rc, _, err = _run(["env", "VIS", "HID"])
    assert rc == 64
    assert "HID" in err


def test_env_missing_name_is_user_error():
    rc, _, _ = _run(["env", "NOPE"])
    assert rc == 64
