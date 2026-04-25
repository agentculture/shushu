from __future__ import annotations

import io
import json
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


def test_doctor_empty_store_reports_pass():
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["summary"]["fail"] == 0


def test_doctor_reports_warn_on_empty_purpose():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    checks = payload["checks"]
    assert any(c["name"] == "purpose" and c["status"] == "WARN" for c in checks), checks


def test_doctor_reports_warn_on_expired_alert():
    import datetime

    store.set_secret(
        name="OLD",
        value="v",
        hidden=False,
        source="localhost",
        purpose="x",
        rotation_howto="rotate",
    )
    store.update_metadata(name="OLD", alert_at=datetime.date(1990, 1, 1))
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    assert any(c["name"] == "alert_at" and c["status"] == "WARN" for c in payload["checks"])
