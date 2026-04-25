from __future__ import annotations

import io
import os
import subprocess  # noqa: S404
import sys
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


def test_run_parses_inject_spec_visible_secret():
    store.set_secret(name="VIS", value="hello", hidden=False, source="localhost", purpose="")
    # Use subprocess to actually exec (so os.execvp doesn't kill the test).
    out = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "shushu",
            "run",
            "--inject",
            "X=VIS",
            "--",
            sys.executable,
            "-c",
            "import os; print(os.environ['X'])",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "hello"


def test_run_hidden_secret_injects_ok():
    store.set_secret(name="HID", value="secret", hidden=True, source="localhost", purpose="")
    out = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "shushu",
            "run",
            "--inject",
            "Y=HID",
            "--",
            sys.executable,
            "-c",
            "import os; print(os.environ['Y'])",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "secret"


def test_run_malformed_inject_is_user_error():
    rc, _, err = _run(["run", "--inject", "=NAME", "--", "/bin/true"])
    assert rc == 64
    assert "VAR=NAME" in err


def test_run_missing_secret_is_user_error():
    rc, _, _ = _run(["run", "--inject", "X=NOPE", "--", "/bin/true"])
    assert rc == 64


def test_run_requires_double_dash_before_cmd():
    rc, _, _ = _run(["run", "--inject", "X=VIS"])  # no cmd
    assert rc == 64


def test_run_duplicate_var_last_wins():
    store.set_secret(name="A", value="one", hidden=False, source="localhost", purpose="")
    store.set_secret(name="B", value="two", hidden=False, source="localhost", purpose="")
    out = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "shushu",
            "run",
            "--inject",
            "X=A",
            "--inject",
            "X=B",
            "--",
            sys.executable,
            "-c",
            "import os; print(os.environ['X'])",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "two"
