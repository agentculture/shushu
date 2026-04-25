from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_show_json_omits_value():
    store.set_secret(name="FOO", value="sensitive", hidden=False, source="localhost", purpose="p")
    rc, out = _run(["show", "FOO", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert "value" not in payload
    assert "sensitive" not in out
    assert payload["name"] == "FOO"


def test_show_missing_is_user_error():
    rc, _ = _run(["show", "NOPE"])
    assert rc == 64
