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


def test_list_empty_prints_nothing_text():
    rc, out = _run(["list"])
    assert rc == 0
    assert out == ""


def test_list_names_sorted_one_per_line():
    for n in ["C", "A", "B"]:
        store.set_secret(name=n, value="v", hidden=False, source="localhost", purpose="")
    rc, out = _run(["list"])
    assert rc == 0
    assert out.splitlines() == ["A", "B", "C"]


def test_list_json():
    store.set_secret(name="X", value="v", hidden=False, source="localhost", purpose="")
    rc, out = _run(["list", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload == {"ok": True, "names": ["X"]}
