from __future__ import annotations

import os
import pwd

import pytest

from shushu import users


def test_current_returns_current_user_info():
    info = users.current()
    expected_name = pwd.getpwuid(os.getuid()).pw_name
    assert info.name == expected_name
    assert info.uid == os.getuid()


def test_resolve_known_user_returns_info():
    expected_name = pwd.getpwuid(os.getuid()).pw_name
    info = users.resolve(expected_name)
    assert info.name == expected_name
    assert info.uid == os.getuid()


def test_resolve_unknown_user_raises():
    with pytest.raises(KeyError):
        users.resolve("definitely-not-a-real-user-xxxxx")


def test_all_users_returns_list_with_entries_having_home_and_name():
    rows = users.all_users()
    assert len(rows) >= 1
    for info in rows:
        assert isinstance(info.name, str)
        assert isinstance(info.uid, int)
