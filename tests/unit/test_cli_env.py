from __future__ import annotations

import subprocess  # noqa: S404

from shushu import store


def test_env_emits_single_quoted_exports(cli_run):
    store.set_secret(name="FOO", value="hello", hidden=False, source="localhost", purpose="")
    store.set_secret(name="BAR", value="world", hidden=False, source="localhost", purpose="")
    rc, out, _ = cli_run(["env", "FOO", "BAR"])
    assert rc == 0
    assert "export FOO='hello'" in out
    assert "export BAR='world'" in out


def test_env_escapes_single_quotes_posix_safe(cli_run):
    store.set_secret(
        name="TRICKY",
        value="it's \"quoted\" and 'risky'",
        hidden=False,
        source="localhost",
        purpose="",
    )
    rc, out, _ = cli_run(["env", "TRICKY"])
    assert rc == 0
    # Round-trip through bash. nosec — bash on PATH, args composed from a
    # value the test itself stores.
    result = subprocess.run(  # noqa: S603, S607
        ["bash", "-c", f'{out.strip()}; printf %s "$TRICKY"'],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "it's \"quoted\" and 'risky'"


def test_env_refuses_when_any_name_is_hidden(cli_run):
    store.set_secret(name="VIS", value="v", hidden=False, source="localhost", purpose="")
    store.set_secret(name="HID", value="h", hidden=True, source="localhost", purpose="")
    rc, _, err = cli_run(["env", "VIS", "HID"])
    assert rc == 64
    assert "HID" in err


def test_env_missing_name_is_user_error(cli_run):
    rc, _, _ = cli_run(["env", "NOPE"])
    assert rc == 64
