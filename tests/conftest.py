"""Shared test fixtures for shushu's unit tests.

`_tmp_home` is autouse so every test gets an isolated `SHUSHU_HOME`
under pytest's `tmp_path`. `cli_run` returns a callable that invokes
`shushu.cli.main` with stdout + stderr captured, so tests don't have
to repeat the `redirect_stdout` / `StringIO` boilerplate.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


@pytest.fixture
def cli_run():
    """Invoke `shushu.cli.main` with captured stdout/stderr.

    Returns a callable `_run(argv) -> (rc, stdout, stderr)`.

    Note: this helper deliberately does NOT catch `SystemExit`. The only
    path that raises it is argparse rejecting unknown args (exit 2) —
    those tests should use `pytest.raises(SystemExit)` instead, so the
    expected exit code is asserted explicitly rather than swallowed.
    """

    def _run(argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main(argv)
        return rc, out.getvalue(), err.getvalue()

    return _run
