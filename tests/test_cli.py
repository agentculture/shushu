from __future__ import annotations

import importlib.metadata
import io
import sys
from contextlib import redirect_stdout

import pytest

from shushu.cli import main


def test_version_flag_prints_package_version():
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    expected = importlib.metadata.version("shushu")
    assert expected in buf.getvalue()


def test_no_args_prints_version_and_exits_success():
    """Until the full CLI lands, the scaffold's 'no args → print version' behaviour holds."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main([])
    assert rc == 0
    assert importlib.metadata.version("shushu") in buf.getvalue()
