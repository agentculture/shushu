from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = main(argv)
    except SystemExit as exc:
        rc = exc.code
    return rc, out.getvalue(), err.getvalue()


def test_get_visible_prints_value():
    store.set_secret(name="FOO", value="bar", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["get", "FOO"])
    assert rc == 0
    assert out.strip() == "bar"


def test_get_hidden_refuses_with_remediation():
    store.set_secret(name="SECRET", value="s", hidden=True, source="localhost", purpose="")
    rc, _, err = _run(["get", "SECRET"])
    assert rc == 64
    assert "hidden" in err.lower()
    assert "inject" in err.lower()


def test_get_missing_is_user_error():
    rc, _, err = _run(["get", "NOPE"])
    assert rc == 64
    assert "NOPE" in err


def test_get_does_not_accept_user_flag():
    # argparse rejects unknown flags with exit 2.
    rc, _, _ = _run(["get", "FOO", "--user", "alice"])
    assert rc == 2
