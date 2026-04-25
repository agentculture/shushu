from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys

from shushu import store


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


def test_run_malformed_inject_is_user_error(cli_run):
    rc, _, err = cli_run(["run", "--inject", "=NAME", "--", "/bin/true"])
    assert rc == 64
    assert "VAR=NAME" in err


def test_run_missing_secret_is_user_error(cli_run):
    rc, _, _ = cli_run(["run", "--inject", "X=NOPE", "--", "/bin/true"])
    assert rc == 64


def test_run_requires_double_dash_before_cmd(cli_run):
    rc, _, _ = cli_run(["run", "--inject", "X=VIS"])  # no cmd
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
