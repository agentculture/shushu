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
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_delete_removes_record():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, _, _ = _run(["delete", "FOO"])
    assert rc == 0
    assert store.list_names() == []


def test_delete_missing_is_user_error():
    rc, _, err = _run(["delete", "NOPE"])
    assert rc == 64
    assert "NOPE" in err
