from __future__ import annotations

import pytest

from shushu import store
from shushu.cli import main


def test_get_visible_prints_value(cli_run):
    store.set_secret(name="FOO", value="bar", hidden=False, source="localhost", purpose="")
    rc, out, _ = cli_run(["get", "FOO"])
    assert rc == 0
    assert out.strip() == "bar"


def test_get_hidden_refuses_with_remediation(cli_run):
    store.set_secret(name="SECRET", value="s", hidden=True, source="localhost", purpose="")
    rc, _, err = cli_run(["get", "SECRET"])
    assert rc == 64
    assert "hidden" in err.lower()
    assert "inject" in err.lower()


def test_get_missing_is_user_error(cli_run):
    rc, _, err = cli_run(["get", "NOPE"])
    assert rc == 64
    assert "NOPE" in err


def test_get_does_not_accept_user_flag():
    # argparse rejects unknown flags by calling sys.exit(2) (raises SystemExit).
    # Use pytest.raises so the expected exit code is asserted explicitly,
    # rather than swallowed by the cli_run helper.
    with pytest.raises(SystemExit) as exc_info:
        main(["get", "FOO", "--user", "alice"])
    assert exc_info.value.code == 2
