"""Integration tests that exercise real setuid-fork handoff.

Gated: skip unless we're root OR SHUSHU_DOCKER=1 is set. CI runs these
inside the disposable integration container.
"""

from __future__ import annotations

import json
import os
import pathlib
import pwd
import stat
import subprocess  # noqa: S404
import sys

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"),
        reason="admin handoff requires root (CI runs this inside a container)",
    ),
]


@pytest.fixture(scope="module")
def two_users():
    """Create two throwaway OS users. Destroyed at module teardown."""
    names = ["shushutest_alice", "shushutest_bob"]
    for n in names:
        subprocess.run(["useradd", "-m", n], check=True)  # noqa: S603, S607
    try:
        yield names
    finally:
        for n in names:
            subprocess.run(["userdel", "-r", n], check=False)  # noqa: S603, S607


def _shushu(*args, env=None):
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "shushu", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_admin_set_writes_as_target_user(two_users):
    alice, _bob = two_users
    r = _shushu("set", "--user", alice, "FOO", "hunter2", "--purpose", "test")
    assert r.returncode == 0, r.stderr
    target = pathlib.Path(pwd.getpwnam(alice).pw_dir) / ".local/share/shushu/secrets.json"
    assert target.exists()
    st = target.stat()
    assert stat.S_IMODE(st.st_mode) == 0o600
    assert st.st_uid == pwd.getpwnam(alice).pw_uid
    payload = json.loads(target.read_text())
    rec = payload["secrets"][0]
    assert rec["name"] == "FOO"
    assert rec["value"] == "hunter2"
    assert rec["source"].startswith("admin:")
    assert rec["handed_over_by"]


def test_admin_set_show_returns_metadata_only(two_users):
    alice, _bob = two_users
    # Ensure alice has FOO set (may already exist from prior test).
    r = _shushu("set", "--user", alice, "FOO", "hunter2", "--purpose", "test")
    assert r.returncode == 0, r.stderr
    # Now run show --user alice FOO --json as root.
    r = _shushu("show", "--user", alice, "FOO", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert "value" not in payload
    assert payload["source"].startswith("admin:")
    assert payload["name"] == "FOO"


def test_admin_generate_hidden_never_shows_value(two_users):
    _alice, bob = two_users
    r = _shushu("generate", "--user", bob, "BOBKEY", "--hidden", "--bytes", "32")
    assert r.returncode == 0, r.stderr
    target = pathlib.Path(pwd.getpwnam(bob).pw_dir) / ".local/share/shushu/secrets.json"
    payload = json.loads(target.read_text())
    # Find the BOBKEY record.
    recs = [s for s in payload["secrets"] if s["name"] == "BOBKEY"]
    assert recs, "BOBKEY not found in bob's store"
    actual_value = recs[0]["value"]
    # The actual value must never appear in stdout or stderr.
    assert actual_value not in r.stdout
    assert actual_value not in r.stderr


def test_admin_delete_removes_secret(two_users):
    alice, _bob = two_users
    # Ensure TO_DELETE exists.
    r = _shushu("set", "--user", alice, "TO_DELETE", "tempval", "--purpose", "temp")
    assert r.returncode == 0, r.stderr
    # Now delete it.
    r = _shushu("delete", "--user", alice, "TO_DELETE")
    assert r.returncode == 0, r.stderr
    # Verify it's gone.
    target = pathlib.Path(pwd.getpwnam(alice).pw_dir) / ".local/share/shushu/secrets.json"
    payload = json.loads(target.read_text())
    names = [s["name"] for s in payload["secrets"]]
    assert "TO_DELETE" not in names


def test_admin_list_user_returns_names(two_users):
    alice, _bob = two_users
    # Ensure alice has at least FOO.
    r = _shushu("set", "--user", alice, "FOO", "hunter2", "--purpose", "test")
    assert r.returncode == 0, r.stderr
    r = _shushu("list", "--user", alice)
    assert r.returncode == 0, r.stderr
    assert "FOO" in r.stdout


def test_target_user_can_inspect_not_admin_field(two_users):
    alice, _ = two_users
    _shushu("set", "--user", alice, "FOO", "v")
    # Drop to alice and run show.
    r = subprocess.run(  # noqa: S603, S607
        ["sudo", "-u", alice, sys.executable, "-m", "shushu", "show", "FOO", "--json"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert "value" not in payload
    assert payload["source"].startswith("admin:")


def test_no_root_owned_files_left_behind(two_users):
    """After the suite, no root-owned files under either user's home."""
    for name in two_users:
        home = pathlib.Path(pwd.getpwnam(name).pw_dir)
        for path in home.rglob("*"):
            st = path.stat()
            assert st.st_uid != 0, f"root-owned leak at {path}"
