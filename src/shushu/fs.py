"""Filesystem primitives for shushu stores.

Responsibilities:
- Path construction (respects SHUSHU_HOME for tests only).
- Directory creation with explicit modes (umask ignored).
- Atomic write: write-to-temp-in-same-dir → fsync → os.replace.
- fcntl advisory locking for concurrent safety.

Does NOT know about JSON, schema, or shushu-specific semantics.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorePaths:
    dir: Path
    file: Path
    lock: Path


def user_store_paths(home: Path | None = None) -> StorePaths:
    """Paths for the store owned by the current process's euid.

    Honors SHUSHU_HOME for tests (placed in a temp dir). In production
    this resolves to ~/.local/share/shushu/.
    """
    override = os.environ.get("SHUSHU_HOME")
    if override:
        base = Path(override)
    else:
        base = (home or Path.home()) / ".local/share/shushu"
    return StorePaths(dir=base, file=base / "secrets.json", lock=base / ".lock")


def ensure_store_dir(paths: StorePaths | None = None) -> StorePaths:
    paths = paths or user_store_paths()
    paths.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Defensive: mkdir with exist_ok=True does NOT chmod an existing dir.
    # Fix up if the dir pre-existed with a wrong mode.
    os.chmod(paths.dir, 0o700)
    # Pre-create an empty lockfile so fcntl has something to hold.
    # O_CREAT (without O_EXCL) is race-safe for concurrent first-run callers:
    # both will open the file; the non-creating caller just gets an fd to
    # the existing lockfile. The chmod below asserts mode 0600 regardless.
    fd = os.open(paths.lock, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    os.chmod(paths.lock, 0o600)
    return paths


def atomic_write_text(target: Path, text: str, mode: int = 0o600) -> None:
    """Atomically replace `target` with `text`. Never leaves a partial file."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


@contextlib.contextmanager
def locked_write(paths: StorePaths | None = None):
    """Exclusive advisory lock for the duration of a write."""
    paths = paths or user_store_paths()
    ensure_store_dir(paths)
    fd = os.open(paths.lock, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextlib.contextmanager
def locked_read(paths: StorePaths | None = None):
    paths = paths or user_store_paths()
    ensure_store_dir(paths)
    fd = os.open(paths.lock, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
