from __future__ import annotations

import json
import os
import stat

from shushu import fs


def test_store_paths_respect_shushu_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))
    paths = fs.user_store_paths()
    assert paths.dir == tmp_path / "shushu"
    assert paths.file == tmp_path / "shushu" / "secrets.json"
    assert paths.lock == tmp_path / "shushu" / ".lock"


def test_store_paths_default_to_home_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SHUSHU_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = fs.user_store_paths()
    assert paths.dir == tmp_path / ".local/share/shushu"


def test_ensure_store_dir_creates_with_mode_0700(tmp_path, monkeypatch):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))
    fs.ensure_store_dir()
    st = (tmp_path / "shushu").stat()
    assert stat.S_IMODE(st.st_mode) == 0o700


def test_atomic_write_text_creates_file_with_mode_0600(tmp_path):
    target = tmp_path / "secrets.json"
    fs.atomic_write_text(target, '{"hello": "world"}\n')
    assert target.read_text() == '{"hello": "world"}\n'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_atomic_write_text_is_crash_safe(tmp_path):
    """On rename, either the old content or the new content is visible.
    Never a half-written file."""
    target = tmp_path / "secrets.json"
    target.write_text('{"v": 1}\n')
    os.chmod(target, 0o600)
    fs.atomic_write_text(target, '{"v": 2}\n')
    assert json.loads(target.read_text()) == {"v": 2}
    # Temp file must be cleaned up.
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith("secrets.json.")]
    assert leftovers == []


def test_locked_write_acquires_exclusive_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))
    fs.ensure_store_dir()
    with fs.locked_write() as lock_fd:
        assert lock_fd > 0  # valid fd
