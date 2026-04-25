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


def test_generate_hex_default_prints_value_once():
    rc, out = _run(["generate", "FOO"])
    assert rc == 0
    # 32 bytes → 64 hex chars
    printed = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    assert any(len(line) == 64 for line in printed)
    assert store.get_value("FOO")  # stored


def test_generate_hidden_does_not_print_value():
    rc, out = _run(["generate", "SECRET", "--hidden"])
    assert rc == 0
    rec = store.get_record("SECRET")
    # The plaintext must NOT appear in stdout.
    assert rec.value not in out
    assert rec.hidden is True


def test_generate_base64_stores_correctly():
    rc, _ = _run(["generate", "FOO", "--encoding", "base64", "--bytes", "16"])
    assert rc == 0
    import base64

    decoded = base64.b64decode(store.get_value("FOO"))
    assert len(decoded) == 16


def test_generate_json_output_never_includes_value_for_hidden():
    rc, out = _run(["generate", "SECRET", "--hidden", "--json"])
    payload = json.loads(out)
    assert "value" not in payload
    assert payload["hidden"] is True
