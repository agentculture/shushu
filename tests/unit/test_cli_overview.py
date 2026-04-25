from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import date

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


def test_overview_json_includes_metadata_but_not_value():
    store.set_secret(name="FOO", value="secret123", hidden=False, source="localhost", purpose="t")
    rc, out = _run(["overview", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    rec = payload["secrets"][0]
    assert rec["name"] == "FOO"
    assert "value" not in rec
    assert "secret123" not in out


def test_overview_expired_filter():
    store.set_secret(name="A", value="v", hidden=False, source="localhost", purpose="x")
    store.set_secret(name="B", value="v", hidden=False, source="localhost", purpose="x")
    store.update_metadata(name="A", alert_at=date(1990, 1, 1))
    rc, out = _run(["overview", "--expired", "--json"])
    payload = json.loads(out)
    names = {r["name"] for r in payload["secrets"]}
    assert names == {"A"}


def test_overview_text_form_shows_alert_markers():
    store.set_secret(name="A", value="v", hidden=False, source="localhost", purpose="x")
    store.update_metadata(name="A", alert_at=date(1990, 1, 1))
    rc, out = _run(["overview"])
    assert rc == 0
    assert "A" in out
    assert "expired" in out.lower()
