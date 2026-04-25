from __future__ import annotations

import os
import shutil

import pytest

from shushu import privilege


def test_require_root_passes_when_euid_is_zero(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    privilege.require_root("set --user alice FOO v")  # no raise


def test_require_root_raises_privilege_error_when_not_root(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with pytest.raises(privilege.PrivilegeError) as exc:
        privilege.require_root("set --user alice FOO v")
    assert "sudo" in exc.value.remediation
    assert "shushu" in exc.value.remediation


def test_sudo_invoker_falls_back_to_getuid_when_sudo_user_unset(monkeypatch):
    monkeypatch.delenv("SUDO_USER", raising=False)
    name = privilege.sudo_invoker()
    assert name  # never empty


def test_sudo_invoker_prefers_sudo_user_when_set(monkeypatch):
    monkeypatch.setenv("SUDO_USER", "alice")
    assert privilege.sudo_invoker() == "alice"


def test_resolve_shushu_path_falls_back_to_plain_name(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert privilege.resolve_shushu_path() == "shushu"


def test_resolve_shushu_path_uses_which_when_available(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/home/alice/.local/bin/shushu")
    assert privilege.resolve_shushu_path() == "/home/alice/.local/bin/shushu"
