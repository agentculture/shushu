from __future__ import annotations

from shushu import store


def test_delete_removes_record(cli_run):
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, _, _ = cli_run(["delete", "FOO"])
    assert rc == 0
    assert store.list_names() == []


def test_delete_missing_is_user_error(cli_run):
    rc, _, err = cli_run(["delete", "NOPE"])
    assert rc == 64
    assert "NOPE" in err
