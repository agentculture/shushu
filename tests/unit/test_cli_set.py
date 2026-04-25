from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv, stdin_text=""):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        orig = sys.stdin
        sys.stdin = io.StringIO(stdin_text)
        try:
            rc = main(argv)
        finally:
            sys.stdin = orig
    return rc, out.getvalue(), err.getvalue()


def test_set_with_value_creates_record():
    rc, _, _ = _run(["set", "FOO", "hunter2", "--purpose", "x"])
    assert rc == 0
    assert store.get_value("FOO") == "hunter2"


def test_set_with_stdin_dash_reads_value():
    rc, _, _ = _run(["set", "FOO", "-"], stdin_text="from-stdin\n")
    assert rc == 0
    # one trailing shell-piped newline stripped
    assert store.get_value("FOO") == "from-stdin"


def test_set_with_stdin_dash_strips_only_one_trailing_newline():
    # If the secret legitimately ends with newlines, only ONE (the
    # shell-piped sentinel) should be stripped.
    rc, _, _ = _run(["set", "FOO", "-"], stdin_text="line-one\nline-two\n\n")
    assert rc == 0
    assert store.get_value("FOO") == "line-one\nline-two\n"


def test_set_without_value_updates_metadata_only():
    store.set_secret(name="FOO", value="orig", hidden=False, source="localhost", purpose="a")
    rc, _, _ = _run(["set", "FOO", "--purpose", "b"])
    assert rc == 0
    assert store.get_value("FOO") == "orig"
    assert store.get_record("FOO").purpose == "b"


def test_set_rejects_changing_source():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, _, err = _run(["set", "FOO", "v2", "--source", "https://other"])
    assert rc == 64
    assert "source is immutable" in err


def test_set_rejects_admin_source_prefix_without_sudo(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    rc, _, err = _run(["set", "FOO", "v", "--source", "admin:ori"])
    assert rc == 64
    assert "admin:" in err


def test_set_rejects_lowercase_name():
    rc, _, _ = _run(["set", "lowercase", "v"])
    assert rc == 64


def test_set_with_alert_at_valid_date():
    rc, _, _ = _run(["set", "FOO", "v", "--alert-at", "2030-01-01"])
    assert rc == 0


def test_set_rejects_invalid_alert_at():
    rc, _, err = _run(["set", "FOO", "v", "--alert-at", "2030-13-40"])
    assert rc == 64
    assert "date" in err.lower()


def test_set_admin_user_without_sudo_is_privilege_error(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    rc, _, err = _run(["set", "--user", "alice", "FOO", "v"])
    assert rc == 66
    assert "sudo" in err
