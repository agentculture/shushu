"""Integration tests for --all-users enumeration (list, overview, doctor).

Gated: skip unless we're root OR SHUSHU_DOCKER=1 is set. CI runs these
inside the disposable integration container.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404
import sys

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"),
        reason="requires root",
    ),
]

_TEST_USER = "shushutest_carol"


@pytest.fixture(scope="module")
def carol_with_secret():
    """Create carol, write a secret as her, yield her name, then tear down."""
    subprocess.run(["useradd", "-m", _TEST_USER], check=True)  # noqa: S603, S607
    try:
        subprocess.run(  # noqa: S603, S607
            [
                "sudo",
                "-u",
                _TEST_USER,
                sys.executable,
                "-m",
                "shushu",
                "set",
                "SEC",
                "supersecret",
                "--purpose",
                "test-secret",
            ],
            check=True,
        )
        yield _TEST_USER
    finally:
        subprocess.run(["userdel", "-r", _TEST_USER], check=False)  # noqa: S603, S607


def _shushu(*args):
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "shushu", *args],
        capture_output=True,
        text=True,
    )


def test_overview_all_users_never_exposes_value(carol_with_secret):
    r = _shushu("overview", "--all-users", "--json")
    assert r.returncode == 0, r.stderr
    assert "supersecret" not in r.stdout
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    users_rows = payload.get("users", [])
    found = [row for row in users_rows if row.get("user") == _TEST_USER]
    assert found, f"{_TEST_USER!r} not in overview output; users={[r['user'] for r in users_rows]}"
    carol_row = found[0]
    # Verify secrets metadata is present but value is absent.
    secrets = carol_row.get("secrets", [])
    assert secrets
    for sec in secrets:
        assert "value" not in sec


def test_list_all_users_returns_names(carol_with_secret):
    r = _shushu("list", "--all-users", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    users_rows = payload.get("users", [])
    found = [row for row in users_rows if row.get("user") == _TEST_USER]
    assert found, f"{_TEST_USER!r} not found in list --all-users output"
    assert "SEC" in found[0]["names"]


def test_doctor_all_users_runs_checks(carol_with_secret):
    r = _shushu("doctor", "--all-users", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    users_rows = payload.get("users", [])
    found = [row for row in users_rows if row.get("user") == _TEST_USER]
    assert found, f"{_TEST_USER!r} not found in doctor --all-users output"
    carol_row = found[0]
    assert "checks" in carol_row
    assert "summary" in carol_row
    # schema_version check should pass.
    sv_checks = [c for c in carol_row["checks"] if c["name"] == "schema_version"]
    assert sv_checks
    assert sv_checks[0]["status"] == "PASS"


def test_list_all_users_text_mode(carol_with_secret):
    r = _shushu("list", "--all-users")
    assert r.returncode == 0, r.stderr
    assert f"# {_TEST_USER}" in r.stdout
    assert "SEC" in r.stdout
