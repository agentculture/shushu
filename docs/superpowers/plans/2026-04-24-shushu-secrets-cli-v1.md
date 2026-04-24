# shushu secrets CLI v1 — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the scaffold `src/shushu/cli.py` into the v1 agent-first secrets manager CLI specified in `docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md`.

**Architecture:** Per-OS-user store at `~/.local/share/shushu/secrets.json` (0600). Stdlib-only Python 3.12. Hard split: `cli/` owns argparse + output; `store.py` owns the JSON file; `privilege.py` owns sudo/setuid-fork for admin handoff. Every handler raises `ShushuError`; dispatch converts to exit code + remediation.

**Tech Stack:** Python ≥ 3.12, stdlib only (`argparse`, `json`, `fcntl`, `pwd`, `secrets`, `base64`, `datetime`, `os`). uv for dev/packaging. pytest + pytest-xdist + pytest-cov. hatchling build.

**Reference docs (read before starting):**
- Design spec: `docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md` (authoritative — when the plan and spec diverge, spec wins; update the plan)
- Sibling reference: `/home/spark/git/zehut/` (same idioms — copy CI workflows, `.markdownlint-cli2.yaml`, `scripts/lint-md.sh`, `.claude/skills/version-bump/` from there and adapt "zehut"→"shushu")
- Pattern origin: `/home/spark/git/afi-cli/` (error discipline + rubric)

**Commit discipline:** Every task ends with a commit. Keep commits small and labelled `feat:`, `test:`, `docs:`, `chore:`, `refactor:` per scope. Never skip pre-commit hooks.

**Version discipline:** This plan lands as version `0.1.0`. The initial repo has `version = "0.1.0"` already; the first task switches `__version__` to `importlib.metadata` so the value is sourced from `pyproject.toml`. **Once work starts, follow per-PR version bumps** via `.claude/skills/version-bump/scripts/bump.py` — patch for each task's commit, minor at the task-group boundaries called out below.

---

## Task 1: Bump Python floor + switch `__version__` to importlib.metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/shushu/__init__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Rewrite the version test to exercise the CLI**

Replace the entire contents of `tests/test_cli.py` with the following. The scaffold test asserted `__version__` equals the `pyproject.toml` literal — after switching to `importlib.metadata` that becomes tautological. The new test asserts `shushu --version` output matches the installed package metadata.

```python
from __future__ import annotations

import importlib.metadata
import io
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: failures (the scaffold prints `shushu 0.1.0`, which still contains the version string, so `test_version_flag_prints_package_version` may pass *by accident* if the literal matches; if so, continue). `test_no_args_prints_version_and_exits_success` should pass. The goal of this step is to record where you start.

- [ ] **Step 3: Rewrite `src/shushu/__init__.py` to source version from metadata**

Replace the whole file with:

```python
"""shushu — agent-first per-OS-user secrets manager."""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("shushu")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    # Only hit when running from a source tree with no editable install.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
```

- [ ] **Step 4: Bump Python floor in `pyproject.toml`**

Apply three edits to `pyproject.toml`:

1. `requires-python = ">=3.10"` → `requires-python = ">=3.12"`.
2. `target-version = ["py310"]` (under `[tool.black]`) → `target-version = ["py312"]`.
3. Replace `authors = [{ name = "Ori Nachum" }]` line with
   `authors = [{ name = "Ori Nachum", email = "ori.nachum@gmail.com" }]` (harmless metadata cleanup).
4. Replace `Homepage` URL `https://github.com/OriNachum/shushu` with `https://github.com/agentculture/shushu`.

- [ ] **Step 5: Reinstall and run tests**

```bash
uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

Expected: both tests in `test_cli.py` pass. If the scaffold had any other tests, they must still pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/shushu/__init__.py tests/test_cli.py
git commit -m "chore: bump Python floor to 3.12; source __version__ from importlib.metadata"
```

---

## Task 2: Refactor `cli.py` into `cli/` package skeleton

Goal: move from one-file argparse to the `cli/` + `cli/_commands/` layout without introducing any new behaviour. `shushu --version` must still work exactly as before.

**Files:**
- Delete: `src/shushu/cli.py`
- Create: `src/shushu/cli/__init__.py`
- Create: `src/shushu/cli/_commands/__init__.py`

- [ ] **Step 1: Read the current `src/shushu/cli.py` to confirm what behaviour we must preserve**

```bash
cat src/shushu/cli.py
```

Expected: the scaffold's argparse `main(argv)` returning an int, handling `--version` and a no-arg default that prints `shushu <version>`.

- [ ] **Step 2: Create the new `cli/` package**

```bash
git mv src/shushu/cli.py src/shushu/cli/__init__.py
mkdir -p src/shushu/cli/_commands
```

(`git mv` into a directory of the same name is a two-step dance — do `git rm src/shushu/cli.py` first if the above fails, then recreate.)

- [ ] **Step 3: Replace the package `__init__.py` contents**

Full contents of `src/shushu/cli/__init__.py`:

```python
"""shushu CLI entry point.

This package will grow `_build_parser` + `_dispatch` + per-verb modules
under `_commands/` as the spec is implemented. For now it preserves the
scaffold's behaviour so the version test stays green.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from shushu import __version__

PROG = "shushu"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="shushu — agent-first per-OS-user secrets manager",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    parser.parse_args(argv)
    # Scaffold behaviour: no args → print version and exit 0.
    print(f"{PROG} {__version__}")
    return 0


__all__ = ["main"]
```

Full contents of `src/shushu/cli/_commands/__init__.py`:

```python
"""Per-verb command modules. Added in later tasks."""
```

- [ ] **Step 4: Confirm `project.scripts` still resolves**

```bash
uv pip install -e ".[dev]"
uv run shushu --version
```

Expected: `shushu 0.1.0` (whatever the current version is).

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/shushu/cli
git commit -m "refactor: split cli.py into cli/ package skeleton"
```

---

## Task 3: Repo chrome — CHANGELOG, markdownlint, lint-md script

**Files:**
- Create: `CHANGELOG.md`
- Create: `.markdownlint-cli2.yaml`
- Create: `scripts/lint-md.sh`

- [ ] **Step 1: Copy `.markdownlint-cli2.yaml` from zehut**

```bash
cp /home/spark/git/zehut/.markdownlint-cli2.yaml .markdownlint-cli2.yaml
```

- [ ] **Step 2: Copy `scripts/lint-md.sh` from zehut**

```bash
mkdir -p scripts
cp /home/spark/git/zehut/scripts/lint-md.sh scripts/lint-md.sh
chmod +x scripts/lint-md.sh
```

Verify: `cat scripts/lint-md.sh` — it should be a short wrapper around `markdownlint-cli2 --fix`.

- [ ] **Step 3: Create `CHANGELOG.md` with an empty Unreleased section**

```markdown
# Changelog

All notable changes to shushu are recorded here. Entries are kept 1:1
with merged PRs per the per-PR version bump discipline documented in
`CLAUDE.md`.

## [Unreleased]

- (nothing yet — v0.1.0 in progress)

## [0.1.0] — 2026-04-24

- Initial scaffold.
```

- [ ] **Step 4: Run markdownlint against the repo**

```bash
npx -y markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: passes on all existing markdown. If it fails, fix the violations before committing.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md .markdownlint-cli2.yaml scripts/lint-md.sh
git commit -m "chore: add CHANGELOG + markdownlint config mirrored from zehut"
```

---

## Task 4: Vendor the version-bump skill

**Files:**
- Create: `.claude/skills/version-bump/SKILL.md`
- Create: `.claude/skills/version-bump/scripts/bump.py`
- Create: `.claude/skills/version-bump/scripts/` (plus any other files present)

- [ ] **Step 1: Copy the skill tree from afi-cli (the canonical source)**

```bash
mkdir -p .claude/skills
cp -r /home/spark/git/afi-cli/.claude/skills/version-bump .claude/skills/version-bump
```

- [ ] **Step 2: Search for any `afi`/`afi-cli`/`zehut` literals in the copied skill and retarget them to `shushu`**

```bash
grep -rn "afi\|zehut" .claude/skills/version-bump
```

Expected: likely zero hits (the script is project-agnostic — it reads `pyproject.toml` in the repo it runs from). If any hits appear, replace with `shushu` via targeted `Edit`.

- [ ] **Step 3: Smoke-test the script**

```bash
echo '{"patch": ["chore: vendor version-bump skill"]}' | python3 .claude/skills/version-bump/scripts/bump.py patch --dry-run 2>&1 | head
```

Expected: prints the computed next version (`0.1.1`) and the CHANGELOG diff it would apply. If `--dry-run` isn't supported, inspect the script to confirm it reads `pyproject.toml` correctly and skip the bump for now.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/version-bump
git commit -m "chore: vendor version-bump skill from afi-cli"
```

---

## Task 5: CI workflows + integration Dockerfile

**Files:**
- Create: `.github/workflows/tests.yml`
- Create: `.github/workflows/publish.yml`
- Create: `.github/workflows/security-checks.yml`
- Create: `.github/workflows/Dockerfile.integration`

- [ ] **Step 1: Copy the four files from zehut**

```bash
mkdir -p .github/workflows
cp /home/spark/git/zehut/.github/workflows/tests.yml .github/workflows/tests.yml
cp /home/spark/git/zehut/.github/workflows/publish.yml .github/workflows/publish.yml
cp /home/spark/git/zehut/.github/workflows/security-checks.yml .github/workflows/security-checks.yml
cp /home/spark/git/zehut/.github/workflows/Dockerfile.integration .github/workflows/Dockerfile.integration
```

- [ ] **Step 2: Replace every `zehut` literal with `shushu`**

```bash
grep -rln zehut .github/workflows/
```

Edit each file found to replace `zehut` with `shushu` case-sensitively. Specifically:
- Package name in `uv sync` / `uv build` steps.
- Any reference to `zehut/` as a source directory → `src/shushu/` (shushu uses src-layout; zehut does not).
- Env-var names `ZEHUT_DOCKER` → `SHUSHU_DOCKER`, `ZEHUT_CONFIG_DIR` / `ZEHUT_STATE_DIR` → `SHUSHU_HOME` (single var for shushu).
- `Dockerfile.integration`: the `COPY zehut ./zehut` line becomes `COPY src ./src`; the `WORKDIR /src` line stays.

- [ ] **Step 3: Verify the src-layout COPY path in the Dockerfile**

Open `.github/workflows/Dockerfile.integration` and confirm it reads (approximately):

```dockerfile
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests ./tests
RUN uv sync
CMD ["uv", "run", "pytest", "-v"]
```

(Drop any `.flake8` COPY if shushu doesn't have that file yet; we configure flake8 in `pyproject.toml`.)

- [ ] **Step 4: Lint the YAML**

```bash
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/tests.yml', '.github/workflows/publish.yml', '.github/workflows/security-checks.yml']]"
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows
git commit -m "ci: adapt workflows from zehut (tests, publish, security, integration Dockerfile)"
```

---

## Task 6: Documentation tree — stubs

The fleshed-out content lands in later tasks. Create the files so references in `CLAUDE.md` and `README.md` resolve.

**Files:**
- Create: `docs/threat-model.md`
- Create: `docs/testing.md`
- Create: `docs/rubric-mapping.md`

- [ ] **Step 1: Create `docs/threat-model.md`**

```markdown
# shushu threat model

(Stub — full content lands in Task 26. Until then, see
`docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md` §8.)
```

- [ ] **Step 2: Create `docs/testing.md`**

```markdown
# shushu testing notes

(Stub — full content lands in Task 26. Documents `SHUSHU_HOME` and
`SHUSHU_DOCKER` env-var hooks used by the test suite.)
```

- [ ] **Step 3: Create `docs/rubric-mapping.md`**

```markdown
# shushu afi-rubric mapping

(Stub — full content lands in Task 26. Maps shushu's CLI to the
afi-cli rubric: `learn`, `explain`, exit-code policy, per-verb JSON
payload schemas.)
```

- [ ] **Step 4: Commit**

```bash
git add docs/threat-model.md docs/testing.md docs/rubric-mapping.md
git commit -m "docs: stub threat-model, testing, rubric-mapping docs"
```

---

## Task 7: `shushu.fs` — paths, locking, atomic write

**Files:**
- Create: `src/shushu/fs.py`
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/unit/test_fs.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/__init__.py`: empty file.

`tests/unit/test_fs.py`:

```python
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_fs.py -v
```

Expected: `ModuleNotFoundError: shushu.fs` or similar.

- [ ] **Step 3: Write `src/shushu/fs.py`**

```python
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
    if not paths.lock.exists():
        fd = os.open(paths.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_fs.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/fs.py tests/unit/__init__.py tests/unit/test_fs.py
git commit -m "feat(fs): paths, locking, atomic write primitives"
```

---

## Task 8: `shushu.alerts` — date classification

**Files:**
- Create: `src/shushu/alerts.py`
- Create: `tests/unit/test_alerts.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_alerts.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from shushu import alerts


def _today(y, m, d):
    return date(y, m, d)


def test_classify_none_returns_ok():
    assert alerts.classify(None, today=_today(2026, 4, 24)) == "ok"


def test_classify_far_future_returns_ok():
    assert alerts.classify(date(2027, 1, 1), today=_today(2026, 4, 24)) == "ok"


def test_classify_within_30_days_returns_alerting():
    assert alerts.classify(date(2026, 5, 10), today=_today(2026, 4, 24)) == "alerting"


def test_classify_today_returns_alerting():
    assert alerts.classify(date(2026, 4, 24), today=_today(2026, 4, 24)) == "alerting"


def test_classify_past_returns_expired():
    assert alerts.classify(date(2026, 4, 23), today=_today(2026, 4, 24)) == "expired"


@pytest.mark.parametrize("s", ["2026-04-24", "2099-12-31"])
def test_parse_date_accepts_iso(s):
    assert alerts.parse_date(s) is not None


def test_parse_date_rejects_malformed():
    with pytest.raises(ValueError):
        alerts.parse_date("2026-13-40")


def test_parse_date_accepts_none_and_empty():
    assert alerts.parse_date(None) is None
    assert alerts.parse_date("") is None
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_alerts.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/shushu/alerts.py`**

```python
"""Alert-date classification for shushu records.

`alert_at` is a date (no time). We compare against today's UTC date.
Classification categories:
- "ok"        — no alert_at, or alert_at is >30 days in the future
- "alerting"  — alert_at is in the next 30 days (inclusive of today)
- "expired"   — alert_at is in the past

This module is pure: no I/O, no store knowledge.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

AlertState = Literal["ok", "alerting", "expired"]

ALERT_WINDOW_DAYS = 30


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def classify(alert_at: date | None, today: date | None = None) -> AlertState:
    if alert_at is None:
        return "ok"
    today = today or today_utc()
    if alert_at < today:
        return "expired"
    if (alert_at - today).days <= ALERT_WINDOW_DAYS:
        return "alerting"
    return "ok"


def parse_date(s: str | None) -> date | None:
    if s is None or s == "":
        return None
    return date.fromisoformat(s)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_alerts.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/alerts.py tests/unit/test_alerts.py
git commit -m "feat(alerts): classify secrets by alert_at vs today (UTC)"
```

---

## Task 9: `shushu.generate` — random + encoding

**Files:**
- Create: `src/shushu/generate.py`
- Create: `tests/unit/test_generate.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_generate.py`:

```python
from __future__ import annotations

import base64

import pytest

from shushu import generate


def test_hex_default_length_is_64_chars_for_32_bytes():
    s = generate.random_secret(nbytes=32, encoding="hex")
    assert len(s) == 64
    int(s, 16)  # must be valid hex


def test_base64_round_trips():
    s = generate.random_secret(nbytes=32, encoding="base64")
    decoded = base64.b64decode(s, validate=True)
    assert len(decoded) == 32


def test_rejects_unknown_encoding():
    with pytest.raises(ValueError):
        generate.random_secret(nbytes=16, encoding="morse")


@pytest.mark.parametrize("n", [1, 8, 16, 32, 64])
def test_variable_byte_lengths(n):
    s = generate.random_secret(nbytes=n, encoding="hex")
    assert len(s) == n * 2


def test_rejects_zero_or_negative_bytes():
    for n in (0, -1):
        with pytest.raises(ValueError):
            generate.random_secret(nbytes=n, encoding="hex")
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_generate.py -v
```

- [ ] **Step 3: Write `src/shushu/generate.py`**

```python
"""Random secret generation.

Wraps `secrets.token_bytes` with hex/base64 encoding. No crypto policy
decisions beyond picking a sensible default size (32 bytes — 256 bits).
"""

from __future__ import annotations

import base64
import secrets as _secrets
from typing import Literal

Encoding = Literal["hex", "base64"]
DEFAULT_BYTES = 32
DEFAULT_ENCODING: Encoding = "hex"


def random_secret(nbytes: int = DEFAULT_BYTES, encoding: Encoding = DEFAULT_ENCODING) -> str:
    if nbytes <= 0:
        raise ValueError(f"nbytes must be positive, got {nbytes}")
    raw = _secrets.token_bytes(nbytes)
    if encoding == "hex":
        return raw.hex()
    if encoding == "base64":
        return base64.b64encode(raw).decode("ascii")
    raise ValueError(f"unknown encoding: {encoding!r} (expected 'hex' or 'base64')")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_generate.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/generate.py tests/unit/test_generate.py
git commit -m "feat(generate): random hex/base64 secret generation"
```

---

## Task 10: `shushu.users` — OS user enumeration & resolution

**Files:**
- Create: `src/shushu/users.py`
- Create: `tests/unit/test_users.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_users.py`:

```python
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
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_users.py -v
```

- [ ] **Step 3: Write `src/shushu/users.py`**

```python
"""OS user enumeration and resolution.

Thin wrapper over `pwd` so the rest of shushu speaks one dataclass.
Used by privilege handoff and admin --all-users enumeration.
"""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserInfo:
    name: str
    uid: int
    gid: int
    home: Path


def _from_pwnam(entry: pwd.struct_passwd) -> UserInfo:
    return UserInfo(
        name=entry.pw_name,
        uid=entry.pw_uid,
        gid=entry.pw_gid,
        home=Path(entry.pw_dir),
    )


def current() -> UserInfo:
    return _from_pwnam(pwd.getpwuid(os.geteuid()))


def resolve(name: str) -> UserInfo:
    return _from_pwnam(pwd.getpwnam(name))


def all_users() -> list[UserInfo]:
    return [_from_pwnam(e) for e in pwd.getpwall()]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_users.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/users.py tests/unit/test_users.py
git commit -m "feat(users): resolve, current, enumerate OS users via pwd"
```

---

## Task 11: `shushu.privilege` — geteuid checks, sudo advice, setuid-fork

**Files:**
- Create: `src/shushu/privilege.py`
- Create: `tests/unit/test_privilege.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_privilege.py`:

```python
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


def test_sudo_invoker_falls_back_to_getuid_when_SUDO_USER_unset(monkeypatch):
    monkeypatch.delenv("SUDO_USER", raising=False)
    name = privilege.sudo_invoker()
    assert name  # never empty


def test_sudo_invoker_prefers_SUDO_USER_when_set(monkeypatch):
    monkeypatch.setenv("SUDO_USER", "alice")
    assert privilege.sudo_invoker() == "alice"


def test_resolve_shushu_path_falls_back_to_plain_name(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert privilege.resolve_shushu_path() == "shushu"


def test_resolve_shushu_path_uses_which_when_available(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/home/alice/.local/bin/shushu")
    assert privilege.resolve_shushu_path() == "/home/alice/.local/bin/shushu"
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_privilege.py -v
```

- [ ] **Step 3: Write `src/shushu/privilege.py`**

```python
"""Privilege handling: euid checks, sudo advice, setuid-fork for handoff.

The setuid-fork helper is the ONLY place in shushu that changes uid/gid.
Every admin-write verb routes through `run_as_user` before touching disk.
"""

from __future__ import annotations

import os
import pwd
import shutil
import sys
from collections.abc import Callable
from typing import NoReturn

from shushu.users import UserInfo


class PrivilegeError(Exception):
    """Raised when an operation requires root and the process is not root."""

    def __init__(self, message: str, remediation: str) -> None:
        super().__init__(message)
        self.message = message
        self.remediation = remediation


def resolve_shushu_path() -> str:
    """Absolute path to the currently-installed shushu executable.

    `uv tool install` places the binary under ~/.local/bin, which is
    typically absent from root's secure_path — so advising `sudo shushu`
    without the resolved path is a common foot-gun. Fall back to `shushu`
    if which() finds nothing (first-install quirk).
    """
    return shutil.which("shushu") or "shushu"


def require_root(command_tail: str) -> None:
    if os.geteuid() == 0:
        return
    path = resolve_shushu_path()
    raise PrivilegeError(
        message="this operation requires root",
        remediation=f"re-run with: sudo {path} {command_tail}",
    )


def sudo_invoker() -> str:
    """Best-guess name of the human who invoked sudo.

    Prefers $SUDO_USER (set by sudo itself). Falls back to the process's
    real uid (which under sudo is the original caller). Guaranteed non-empty.
    """
    name = os.environ.get("SUDO_USER")
    if name:
        return name
    return pwd.getpwuid(os.getuid()).pw_name


def run_as_user(user: UserInfo, fn: Callable[[], int]) -> int:
    """Fork a child, drop to (user.uid, user.gid), call fn(), exit with its return code.

    Must be invoked with geteuid() == 0 in the parent. Returns the child's
    exit status to the parent.
    """
    if os.geteuid() != 0:
        raise PrivilegeError(
            message="run_as_user requires euid=0 in the parent",
            remediation="this is a programming error; admin handlers must call require_root first",
        )
    pid = os.fork()
    if pid == 0:  # child
        _become(user)
        try:
            rc = fn()
        except PrivilegeError as exc:
            sys.stderr.write(f"shushu: error: {exc.message}\n  → {exc.remediation}\n")
            os._exit(66)
        except Exception as exc:  # pragma: no cover
            sys.stderr.write(f"shushu: internal error in admin handoff: {exc!r}\n")
            os._exit(70)
        os._exit(rc)
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return 67  # EXIT_BACKEND — child died abnormally


def _become(user: UserInfo) -> None:
    """Switch identity. Order matters: setgroups → setgid → setuid."""
    os.setgroups([])
    os.setgid(user.gid)
    os.setegid(user.gid)
    os.setuid(user.uid)
    os.seteuid(user.uid)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_privilege.py -v
```

Expected: all pass. (The `run_as_user` function itself is exercised in integration tests — it needs real root.)

- [ ] **Step 5: Commit**

```bash
git add src/shushu/privilege.py tests/unit/test_privilege.py
git commit -m "feat(privilege): require_root, sudo_invoker, setuid-fork run_as_user"
```

---

## Task 12: `shushu.store` — the JSON secret store

Most complex module. Depends on `fs`, `alerts`, indirectly on `users` / `privilege`. No CLI knowledge.

**Files:**
- Create: `src/shushu/store.py`
- Create: `tests/unit/test_store.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_store.py`:

```python
from __future__ import annotations

import json
from datetime import date

import pytest

from shushu import store


@pytest.fixture(autouse=True)
def _tmp_store(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def test_load_returns_empty_when_no_file():
    data = store.load()
    assert data.schema_version == 1
    assert data.secrets == []


def test_set_then_load_roundtrips():
    rec = store.set_secret(
        name="FOO",
        value="bar",
        hidden=False,
        source="localhost",
        purpose="test",
    )
    assert rec.name == "FOO"
    data = store.load()
    assert len(data.secrets) == 1
    assert data.secrets[0].name == "FOO"
    assert data.secrets[0].value == "bar"


def test_overwrite_silently_replaces_value():
    store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    store.set_secret(name="FOO", value="v2", hidden=False, source="localhost", purpose="")
    data = store.load()
    assert len(data.secrets) == 1
    assert data.secrets[0].value == "v2"


def test_overwrite_preserves_created_at_and_handed_over_by():
    first = store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    second = store.set_secret(name="FOO", value="v2", hidden=False, source="localhost", purpose="")
    assert first.created_at == second.created_at
    assert first.handed_over_by == second.handed_over_by


def test_set_rejects_invalid_name():
    with pytest.raises(store.ValidationError):
        store.set_secret(
            name="lowercase-bad",
            value="v",
            hidden=False,
            source="localhost",
            purpose="",
        )


def test_update_metadata_only():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="orig")
    store.update_metadata(name="FOO", purpose="new")
    data = store.load()
    assert data.secrets[0].purpose == "new"
    assert data.secrets[0].value == "v"  # untouched


def test_update_metadata_rejects_immutable_fields():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    with pytest.raises(store.ValidationError):
        store.update_metadata(name="FOO", source="forbidden")  # type: ignore[arg-type]


def test_update_metadata_rejects_unknown_secret():
    with pytest.raises(store.NotFoundError):
        store.update_metadata(name="NOPE", purpose="x")


def test_get_value_raises_on_hidden():
    store.set_secret(name="SECRET", value="s", hidden=True, source="localhost", purpose="")
    with pytest.raises(store.HiddenError):
        store.get_value("SECRET")


def test_get_value_returns_visible():
    store.set_secret(name="VISIBLE", value="hello", hidden=False, source="localhost", purpose="")
    assert store.get_value("VISIBLE") == "hello"


def test_delete_removes_record():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    store.delete("FOO")
    assert store.load().secrets == []


def test_delete_missing_raises_not_found():
    with pytest.raises(store.NotFoundError):
        store.delete("NOPE")


def test_list_names_sorted():
    for n in ["BAZ", "FOO", "BAR"]:
        store.set_secret(name=n, value="v", hidden=False, source="localhost", purpose="")
    assert store.list_names() == ["BAR", "BAZ", "FOO"]


def test_schema_version_mismatch_raises():
    paths = store._paths()
    paths.dir.mkdir(parents=True, exist_ok=True)
    paths.file.write_text(json.dumps({"schema_version": 99, "secrets": []}))
    with pytest.raises(store.StateError) as exc:
        store.load()
    assert "schema_version" in str(exc.value)


def test_alert_at_parsed_and_stored():
    store.set_secret(
        name="FOO",
        value="v",
        hidden=False,
        source="localhost",
        purpose="",
        alert_at=date(2030, 1, 1),
    )
    rec = store.load().secrets[0]
    assert rec.alert_at == date(2030, 1, 1)
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_store.py -v
```

- [ ] **Step 3: Write `src/shushu/store.py`**

```python
"""Per-user secrets store on disk. Single source of truth for secrets.json.

Responsibilities:
- Load/save JSON under the per-user store dir.
- Enforce schema_version and record-field validation.
- Enforce immutability: source / hidden / created_at / handed_over_by / name.
- Provide CRUD: set_secret, update_metadata, get_value, delete, list_names.
- Expose typed errors for the CLI layer to turn into ShushuError exit codes.

Does NOT know about sudo, argparse, or output formatting.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from shushu import fs

SCHEMA_VERSION = 1
NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")

# --- typed errors --------------------------------------------------------

class StoreError(Exception):
    """Base for store-level errors that the CLI translates to exit codes."""


class ValidationError(StoreError):
    """Input failed validation (bad name, bad date, immutable field)."""


class NotFoundError(StoreError):
    """Secret name not present in the store."""


class HiddenError(StoreError):
    """Attempt to read value of a hidden secret."""


class StateError(StoreError):
    """Store file corrupt / schema_version mismatch / unreadable."""


# --- dataclasses ---------------------------------------------------------

@dataclass(frozen=True)
class SecretRecord:
    name: str
    value: str
    hidden: bool
    source: str
    purpose: str
    rotation_howto: str
    alert_at: date | None
    handed_over_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoreData:
    schema_version: int
    secrets: list[SecretRecord] = field(default_factory=list)


# --- serialization -------------------------------------------------------

def _record_to_json(r: SecretRecord) -> dict[str, Any]:
    return {
        "name": r.name,
        "value": r.value,
        "hidden": r.hidden,
        "source": r.source,
        "purpose": r.purpose,
        "rotation_howto": r.rotation_howto,
        "alert_at": r.alert_at.isoformat() if r.alert_at else None,
        "handed_over_by": r.handed_over_by,
        "created_at": _dt_to_str(r.created_at),
        "updated_at": _dt_to_str(r.updated_at),
    }


def _json_to_record(d: dict[str, Any]) -> SecretRecord:
    return SecretRecord(
        name=d["name"],
        value=d["value"],
        hidden=bool(d["hidden"]),
        source=d["source"],
        purpose=d.get("purpose", ""),
        rotation_howto=d.get("rotation_howto", ""),
        alert_at=date.fromisoformat(d["alert_at"]) if d.get("alert_at") else None,
        handed_over_by=d.get("handed_over_by"),
        created_at=_str_to_dt(d["created_at"]),
        updated_at=_str_to_dt(d["updated_at"]),
    )


def _dt_to_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _str_to_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --- load / save ---------------------------------------------------------

def _paths() -> fs.StorePaths:
    return fs.user_store_paths()


def load() -> StoreData:
    paths = _paths()
    if not paths.file.exists():
        return StoreData(schema_version=SCHEMA_VERSION, secrets=[])
    try:
        with fs.locked_read(paths):
            raw = json.loads(paths.file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"secrets.json is not valid JSON: {exc}")
    sv = raw.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise StateError(
            f"store schema_version={sv} but this binary supports {SCHEMA_VERSION}"
        )
    try:
        secrets = [_json_to_record(d) for d in raw.get("secrets", [])]
    except (KeyError, ValueError) as exc:
        raise StateError(f"secrets.json contains malformed record: {exc}")
    return StoreData(schema_version=SCHEMA_VERSION, secrets=secrets)


def _save(data: StoreData) -> None:
    paths = _paths()
    with fs.locked_write(paths):
        payload = {
            "schema_version": data.schema_version,
            "secrets": [_record_to_json(r) for r in data.secrets],
        }
        fs.atomic_write_text(paths.file, json.dumps(payload, indent=2) + "\n")


# --- validation ----------------------------------------------------------

def _validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValidationError(
            f"invalid name {name!r}; must match {NAME_RE.pattern} "
            "(uppercase + underscore + digits, starts with letter/_, ≤64 chars)"
        )


# --- mutations -----------------------------------------------------------

IMMUTABLE_FIELDS = ("source", "hidden", "created_at", "handed_over_by", "name")
MUTABLE_META_FIELDS = ("purpose", "rotation_howto", "alert_at")


def set_secret(
    *,
    name: str,
    value: str,
    hidden: bool,
    source: str,
    purpose: str,
    rotation_howto: str = "",
    alert_at: date | None = None,
    handed_over_by: str | None = None,
) -> SecretRecord:
    """Create or overwrite the named secret. Overwrite preserves
    created_at, source, hidden, handed_over_by (all immutable)."""
    _validate_name(name)
    data = load()
    existing = _find(data, name)
    now = _now_utc()
    if existing is None:
        rec = SecretRecord(
            name=name,
            value=value,
            hidden=hidden,
            source=source,
            purpose=purpose,
            rotation_howto=rotation_howto,
            alert_at=alert_at,
            handed_over_by=handed_over_by,
            created_at=now,
            updated_at=now,
        )
        new_secrets = [*data.secrets, rec]
    else:
        # Overwrite: value changes; immutables stay; mutables may change
        # if the caller passed new ones. For v1, set_secret-with-value
        # preserves all metadata unless new flags were explicitly given.
        # The CLI layer is responsible for not passing new source/hidden
        # on overwrite; store enforces the invariant via update_metadata.
        if existing.source != source:
            raise ValidationError(
                "source is immutable post-create; delete and re-create to change"
            )
        if existing.hidden != hidden:
            raise ValidationError(
                "hidden is immutable post-create; delete and re-create to change"
            )
        rec = SecretRecord(
            name=existing.name,
            value=value,
            hidden=existing.hidden,
            source=existing.source,
            purpose=purpose or existing.purpose,
            rotation_howto=rotation_howto or existing.rotation_howto,
            alert_at=alert_at if alert_at is not None else existing.alert_at,
            handed_over_by=existing.handed_over_by,
            created_at=existing.created_at,
            updated_at=now,
        )
        new_secrets = [r if r.name != name else rec for r in data.secrets]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
    return rec


def update_metadata(
    *,
    name: str,
    purpose: str | None = None,
    rotation_howto: str | None = None,
    alert_at: date | None = None,
    **forbidden: Any,
) -> SecretRecord:
    """Update only mutable metadata. Refuses attempts to touch immutables."""
    if forbidden:
        bad = next(iter(forbidden))
        raise ValidationError(
            f"{bad!r} is immutable post-create; "
            "delete and re-create to change it"
        )
    data = load()
    existing = _find(data, name)
    if existing is None:
        raise NotFoundError(f"no secret named {name}")
    rec = SecretRecord(
        name=existing.name,
        value=existing.value,
        hidden=existing.hidden,
        source=existing.source,
        purpose=purpose if purpose is not None else existing.purpose,
        rotation_howto=(
            rotation_howto if rotation_howto is not None else existing.rotation_howto
        ),
        alert_at=alert_at if alert_at is not None else existing.alert_at,
        handed_over_by=existing.handed_over_by,
        created_at=existing.created_at,
        updated_at=_now_utc(),
    )
    new_secrets = [r if r.name != name else rec for r in data.secrets]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
    return rec


def get_value(name: str) -> str:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    if rec.hidden:
        raise HiddenError(
            f"{name} is a hidden secret; use `shushu run --inject VAR={name} -- <cmd>`"
        )
    return rec.value


def get_record(name: str) -> SecretRecord:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    return rec


def delete(name: str) -> None:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    new_secrets = [r for r in data.secrets if r.name != name]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))


def list_names() -> list[str]:
    return sorted(r.name for r in load().secrets)


def _find(data: StoreData, name: str) -> SecretRecord | None:
    for r in data.secrets:
        if r.name == name:
            return r
    return None
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_store.py -v
```

Expected: all 15 tests pass. If any fail, fix the implementation until they do — this module is the core; correctness here is non-negotiable.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/store.py tests/unit/test_store.py
git commit -m "feat(store): schema-enforced JSON CRUD with immutability guards"
```

---

## Task 13: `cli/_errors.py` + `cli/_output.py`

**Files:**
- Create: `src/shushu/cli/_errors.py`
- Create: `src/shushu/cli/_output.py`
- Create: `tests/unit/test_errors.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_errors.py`:

```python
from __future__ import annotations

import io
import json

from shushu.cli._errors import EXIT_USER_ERROR, EXIT_INTERNAL, ShushuError
from shushu.cli._output import emit_error, emit_result


def test_emit_error_text_single_line():
    buf = io.StringIO()
    emit_error(
        ShushuError(EXIT_USER_ERROR, "FOO is hidden", "use `shushu run --inject`"),
        json_mode=False,
        stream=buf,
    )
    line = buf.getvalue()
    assert line.count("\n") == 1
    assert "shushu: error: FOO is hidden" in line
    assert "use `shushu run --inject`" in line


def test_emit_error_json_structured():
    buf = io.StringIO()
    emit_error(
        ShushuError(EXIT_USER_ERROR, "FOO is hidden", "use inject"),
        json_mode=True,
        stream=buf,
    )
    payload = json.loads(buf.getvalue())
    assert payload == {
        "ok": False,
        "error": {
            "code": 64,
            "name": "EXIT_USER_ERROR",
            "message": "FOO is hidden",
            "remediation": "use inject",
        },
    }


def test_emit_result_text_noop_on_none():
    buf = io.StringIO()
    emit_result(None, json_mode=False, stream=buf)
    assert buf.getvalue() == ""


def test_emit_result_json_wraps_payload_in_ok_true():
    buf = io.StringIO()
    emit_result({"name": "FOO"}, json_mode=True, stream=buf)
    payload = json.loads(buf.getvalue())
    assert payload == {"ok": True, "name": "FOO"}
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_errors.py -v
```

- [ ] **Step 3: Write `src/shushu/cli/_errors.py`**

```python
"""Error discipline: ShushuError + EXIT_* constants.

Every handler raises ShushuError. The dispatcher catches and routes
through _output.emit_error. Unknown exceptions wrap to EXIT_INTERNAL.
"""

from __future__ import annotations

EXIT_SUCCESS = 0
EXIT_USER_ERROR = 64
EXIT_STATE = 65
EXIT_PRIVILEGE = 66
EXIT_BACKEND = 67
EXIT_CONFLICT = 68
EXIT_INTERNAL = 70

_EXIT_NAMES = {
    EXIT_SUCCESS: "EXIT_SUCCESS",
    EXIT_USER_ERROR: "EXIT_USER_ERROR",
    EXIT_STATE: "EXIT_STATE",
    EXIT_PRIVILEGE: "EXIT_PRIVILEGE",
    EXIT_BACKEND: "EXIT_BACKEND",
    EXIT_CONFLICT: "EXIT_CONFLICT",
    EXIT_INTERNAL: "EXIT_INTERNAL",
}


class ShushuError(Exception):
    """Structured error: exit code + human message + remediation."""

    def __init__(self, code: int, message: str, remediation: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation

    @property
    def name(self) -> str:
        return _EXIT_NAMES.get(self.code, f"EXIT_{self.code}")
```

- [ ] **Step 4: Write `src/shushu/cli/_output.py`**

```python
"""Output helpers: text vs. JSON modes.

Rules:
- `--json` → ONE JSON object on stdout, nothing else.
- Text mode → concise human output on stdout; warnings go to stderr.
- Errors share the same shape (text vs. JSON) and always include a
  remediation field.
"""

from __future__ import annotations

import json
import sys
from typing import Any, IO

from shushu.cli._errors import ShushuError


def emit_result(payload: Any, *, json_mode: bool, stream: IO[str] | None = None) -> None:
    stream = stream or sys.stdout
    if json_mode:
        wrapped = {"ok": True}
        if isinstance(payload, dict):
            wrapped.update(payload)
        elif payload is not None:
            wrapped["result"] = payload
        stream.write(json.dumps(wrapped) + "\n")
    elif payload is None:
        return
    else:
        if isinstance(payload, str):
            stream.write(payload)
            if not payload.endswith("\n"):
                stream.write("\n")
        else:
            stream.write(str(payload) + "\n")


def emit_error(err: ShushuError, *, json_mode: bool, stream: IO[str] | None = None) -> None:
    stream = stream or sys.stderr
    if json_mode:
        payload = {
            "ok": False,
            "error": {
                "code": err.code,
                "name": err.name,
                "message": err.message,
                "remediation": err.remediation,
            },
        }
        stream.write(json.dumps(payload) + "\n")
    else:
        stream.write(f"shushu: error: {err.message}; {err.remediation}\n")


def emit_warning(message: str, *, json_mode: bool) -> None:
    """Warnings always go to stderr, regardless of json_mode, so agent
    stdout parsing stays clean."""
    if not json_mode:
        sys.stderr.write(f"shushu: warning: {message}\n")
    # In json_mode we suppress warnings entirely (payloads carry their own
    # structured alert info when relevant).
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/shushu/cli/_errors.py src/shushu/cli/_output.py tests/unit/test_errors.py
git commit -m "feat(cli): ShushuError + structured text/JSON output helpers"
```

---

## Task 14: CLI parser skeleton with dispatch wired to stub handlers

Goal: every verb from the spec exists in the parser; dispatch routes to per-verb modules; every handler raises `NotImplementedError` for now. Subsequent tasks replace stubs with real bodies.

**Files:**
- Modify: `src/shushu/cli/__init__.py`
- Create: 12 stub files under `src/shushu/cli/_commands/`:
  `doctor.py`, `learn.py`, `explain.py`, `overview.py`, `set.py`, `show.py`,
  `get.py`, `env.py`, `run.py`, `generate.py`, `list.py` (renamed to `list_.py` to avoid shadowing stdlib), `delete.py`.

- [ ] **Step 1: Create stub files**

Each stub file has the same minimal contents. Create `src/shushu/cli/_commands/doctor.py` with:

```python
from __future__ import annotations


def handle(args) -> int:
    raise NotImplementedError("doctor: implemented in Task 16")
```

Repeat for each of the 12 commands — replace the task number in the message:
- `learn.py` → Task 15
- `explain.py` → Task 15
- `overview.py` → Task 17
- `set.py` → Task 18
- `show.py` → Task 20
- `get.py` → Task 21
- `env.py` → Task 22
- `run.py` → Task 23
- `generate.py` → Task 19
- `list_.py` → Task 24
- `delete.py` → Task 25

- [ ] **Step 2: Replace `src/shushu/cli/__init__.py` with the full parser**

```python
"""shushu CLI entry point: parser + dispatch + error routing."""

from __future__ import annotations

import argparse
import traceback
from collections.abc import Sequence

from shushu import __version__
from shushu.cli import _output
from shushu.cli._commands import (
    delete,
    doctor,
    env,
    explain,
    generate,
    get,
    learn,
    list_,
    overview,
    run,
    set as set_cmd,
    show,
)
from shushu.cli._errors import EXIT_INTERNAL, EXIT_SUCCESS, EXIT_USER_ERROR, ShushuError

PROG = "shushu"

_HANDLERS = {
    "doctor": doctor.handle,
    "overview": overview.handle,
    "learn": learn.handle,
    "explain": explain.handle,
    "set": set_cmd.handle,
    "show": show.handle,
    "get": get.handle,
    "env": env.handle,
    "run": run.handle,
    "generate": generate.handle,
    "list": list_.handle,
    "delete": delete.handle,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=PROG, description="shushu — agent-first secrets manager")
    p.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    # globals
    sub.add_parser("doctor", help="Store health / integrity checks").add_argument(
        "--json", action="store_true"
    )
    sub.add_parser("learn", help="Agent-authored self-teaching output").add_argument(
        "--json", action="store_true"
    )
    pe = sub.add_parser("explain", help="Explain a command or concept")
    pe.add_argument("topic")

    po = sub.add_parser("overview", help="Rich metadata snapshot")
    po.add_argument("--json", action="store_true")
    po.add_argument("--expired", action="store_true")
    _add_admin_flags(po)

    # secret verbs
    ps = sub.add_parser("set", help="Create or update a secret")
    ps.add_argument("name")
    ps.add_argument("value", nargs="?")
    ps.add_argument("--source")
    ps.add_argument("--purpose")
    ps.add_argument("--rotate-howto", dest="rotate_howto")
    ps.add_argument("--alert-at", dest="alert_at")
    ps.add_argument("--hidden", action="store_true")
    ps.add_argument("--json", action="store_true")
    _add_admin_flags(ps, all_users=False)

    psh = sub.add_parser("show", help="Show metadata (never value)")
    psh.add_argument("name")
    psh.add_argument("--json", action="store_true")
    _add_admin_flags(psh, all_users=False)

    pg = sub.add_parser("get", help="Print value (refuses hidden)")
    pg.add_argument("name")
    pg.add_argument("--json", action="store_true")

    pe2 = sub.add_parser("env", help="Emit shell export lines")
    pe2.add_argument("names", nargs="+")

    pr = sub.add_parser("run", help="Spawn a subprocess with injected secrets")
    pr.add_argument("--inject", action="append", required=True, metavar="VAR=NAME")
    pr.add_argument("cmd_and_args", nargs=argparse.REMAINDER)

    pgn = sub.add_parser("generate", help="Create a random secret")
    pgn.add_argument("name")
    pgn.add_argument("--bytes", dest="nbytes", type=int, default=32)
    pgn.add_argument("--encoding", choices=["hex", "base64"], default="hex")
    pgn.add_argument("--source")
    pgn.add_argument("--purpose")
    pgn.add_argument("--rotate-howto", dest="rotate_howto")
    pgn.add_argument("--alert-at", dest="alert_at")
    pgn.add_argument("--hidden", action="store_true")
    pgn.add_argument("--json", action="store_true")
    _add_admin_flags(pgn, all_users=False)

    pl = sub.add_parser("list", help="Names-only listing")
    pl.add_argument("--json", action="store_true")
    _add_admin_flags(pl)

    pd = sub.add_parser("delete", help="Remove a secret")
    pd.add_argument("name")
    pd.add_argument("--json", action="store_true")
    _add_admin_flags(pd, all_users=False)

    return p


def _add_admin_flags(p: argparse.ArgumentParser, *, all_users: bool = True) -> None:
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--user", metavar="NAME", help="(sudo) operate on another user's store")
    if all_users:
        grp.add_argument("--all-users", action="store_true", help="(sudo, read-only) operate across all users")


def _dispatch(args: argparse.Namespace) -> int:
    handler = _HANDLERS.get(args.cmd)
    if handler is None:
        _build_parser().print_help()
        return EXIT_SUCCESS
    return handler(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    json_mode = getattr(args, "json", False)
    if args.cmd is None:
        print(f"{PROG} {__version__}")
        return EXIT_SUCCESS
    try:
        return _dispatch(args)
    except ShushuError as exc:
        _output.emit_error(exc, json_mode=json_mode)
        return exc.code
    except NotImplementedError as exc:
        _output.emit_error(
            ShushuError(EXIT_USER_ERROR, f"not implemented: {exc}", "coming in a later task"),
            json_mode=json_mode,
        )
        return EXIT_USER_ERROR
    except Exception as exc:  # pragma: no cover
        tb = traceback.format_exc()
        _output.emit_error(
            ShushuError(
                EXIT_INTERNAL,
                f"unexpected error: {exc!r}",
                "please file an issue at github.com/agentculture/shushu/issues with the above",
            ),
            json_mode=json_mode,
        )
        import sys
        sys.stderr.write(tb)
        return EXIT_INTERNAL


__all__ = ["main"]
```

- [ ] **Step 3: Run the existing tests to confirm nothing broke**

```bash
uv run pytest tests/ -v
```

Expected: existing tests still pass. `shushu --version` still works. `shushu doctor` returns 64 with "not implemented" message (confirming the stub dispatch path).

- [ ] **Step 4: Smoke-test the CLI**

```bash
uv run shushu --version
uv run shushu --help
uv run shushu doctor || echo "exit=$?"
```

Expected: version prints; help lists every subcommand; `doctor` exits 64 with remediation "coming in a later task".

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/__init__.py src/shushu/cli/_commands/
git commit -m "feat(cli): argparse skeleton with all verbs wired to stub handlers"
```

---

## Task 15: `learn` + `explain` global verbs

**Files:**
- Modify: `src/shushu/cli/_commands/learn.py`
- Modify: `src/shushu/cli/_commands/explain.py`
- Create: `tests/unit/test_cli_globals.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_globals.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu.cli import main


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_learn_text_mentions_every_verb():
    rc, out, _ = _run(["learn"])
    assert rc == 0
    for verb in ["set", "show", "get", "env", "run", "generate", "list", "delete", "overview", "doctor"]:
        assert verb in out


def test_learn_json_returns_ok_true_and_verb_index():
    rc, out, _ = _run(["learn", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert "verbs" in payload
    assert set(payload["verbs"]) >= {"set", "show", "get", "env", "run", "generate", "list", "delete", "overview", "doctor"}


def test_explain_known_verb_returns_markdown():
    rc, out, _ = _run(["explain", "set"])
    assert rc == 0
    assert "set" in out.lower()


def test_explain_known_concept():
    rc, out, _ = _run(["explain", "hidden"])
    assert rc == 0
    assert "hidden" in out.lower()


def test_explain_unknown_topic_is_user_error():
    rc, _, err = _run(["explain", "definitely-not-a-topic"])
    assert rc == 64
    assert "definitely-not-a-topic" in err
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_globals.py -v
```

- [ ] **Step 3: Implement `learn.py`**

Replace `src/shushu/cli/_commands/learn.py` with:

```python
"""`shushu learn` — agent-authored self-teaching output."""

from __future__ import annotations

from shushu.cli._output import emit_result

_VERBS = {
    "set": "Create or update a secret. With value: writes value + metadata. Without value: updates mutable metadata only.",
    "show": "Print full metadata for a secret (never value).",
    "get": "Print value to stdout. Refused if hidden.",
    "env": "Emit shell export lines for eval. Refused if any named secret is hidden.",
    "run": "Spawn a command with secrets injected as env vars. Works for hidden and non-hidden.",
    "generate": "Create a random secret (hex or base64). --hidden to make it write-only-via-inject.",
    "list": "Names only, one per line. Scriptable.",
    "delete": "Remove a secret.",
    "overview": "Rich metadata snapshot; alert classification; --expired filter.",
    "doctor": "Setup / permission / schema integrity checks.",
    "learn": "What you are reading.",
    "explain": "Human-readable docs for a verb or concept (e.g. `shushu explain hidden`).",
}

_CONCEPTS = [
    "Hidden secrets can only be consumed via `shushu run --inject`. get/env refuse them.",
    "Admin mode: `sudo shushu <verb> --user <name>` writes into another user's store via setuid-fork.",
    "The CLI never prints values in admin mode — even for root. Use `sudo cat` for plaintext.",
    "Every destructive op is silent-overwrite; there is no rollback in v1.",
    "alert_at is informational — shushu never deletes or refuses based on it.",
]


def handle(args) -> int:
    if args.json:
        emit_result({"verbs": sorted(_VERBS.keys()), "descriptions": _VERBS, "concepts": _CONCEPTS}, json_mode=True)
        return 0
    lines = ["# shushu — agent-first per-OS-user secrets manager", ""]
    lines.append("## Verbs")
    for verb in sorted(_VERBS):
        lines.append(f"- `{verb}` — {_VERBS[verb]}")
    lines.append("")
    lines.append("## Concepts")
    for c in _CONCEPTS:
        lines.append(f"- {c}")
    emit_result("\n".join(lines), json_mode=False)
    return 0
```

- [ ] **Step 4: Implement `explain.py`**

Replace `src/shushu/cli/_commands/explain.py` with:

```python
"""`shushu explain <topic>` — short markdown docs per topic."""

from __future__ import annotations

from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result

_TOPICS = {
    "set": "`shushu set NAME [value] [--flags]`\n\nCreate or update. With value: writes value + metadata. Without value: updates mutable metadata only (`--purpose`, `--rotate-howto`, `--alert-at`). `source` and `hidden` are immutable post-create. Use `-` for value to read from stdin (preferred for real secrets).",
    "show": "`shushu show NAME [--json]`\n\nPrint metadata (name, source, purpose, rotation_howto, alert_at, hidden, handed_over_by, timestamps). Never prints `value`.",
    "get": "`shushu get NAME`\n\nPrint value to stdout. Refuses if the secret is hidden (use `shushu run --inject`).",
    "env": "`shushu env NAME1 [NAME2 ...]`\n\nPrint POSIX shell export lines for `eval $(shushu env FOO BAR)`. Refuses if any named secret is hidden.",
    "run": "`shushu run --inject VAR=NAME [--inject ...] -- cmd [args...]`\n\nFork, set env vars from the store, `execvp` the command. Works for hidden and non-hidden.",
    "generate": "`shushu generate NAME [--bytes N] [--encoding hex|base64] [flags]`\n\nCreate a random secret. Defaults to 32 bytes hex. `--hidden` → never prints value.",
    "list": "`shushu list [--json] [--user NAME|--all-users]`\n\nNames only, one per line. Scriptable.",
    "delete": "`shushu delete NAME`\n\nRemove a secret. No undo.",
    "overview": "`shushu overview [--json] [--expired] [--user NAME|--all-users]`\n\nRich metadata snapshot with alert classification.",
    "doctor": "`shushu doctor [--json] [--user NAME|--all-users]`\n\nVerify store dir, file modes, schema_version, and per-record validity.",
    "hidden": "A *hidden* secret has `hidden: true`. It is immutable — you cannot toggle it. The CLI refuses to print its value via `get` or `env`; only `shushu run --inject` can consume it. Note: the file is still plaintext on disk (mode 0600). `hidden` is a CLI contract, not cryptography.",
    "admin": "Admin mode is `sudo shushu <verb> --user NAME` (or `--all-users` for reads). shushu forks, drops to the target user's uid/gid, then writes as that user. The target user owns the resulting file. Admin *cannot* read values through the CLI — even for root. Use `sudo cat` for plaintext.",
    "alert_at": "Optional ISO date (`YYYY-MM-DD`). `overview` classifies records as ok / alerting (within 30 days) / expired. shushu never enforces expiry — the date is informational.",
}


def handle(args) -> int:
    topic = args.topic
    body = _TOPICS.get(topic)
    if body is None:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"no topic {topic!r}",
            "try: shushu explain set | hidden | admin | alert_at (or any verb name)",
        )
    emit_result(body, json_mode=False)
    return 0
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_cli_globals.py -v
```

Expected: all 5 pass.

- [ ] **Step 6: Commit**

```bash
git add src/shushu/cli/_commands/learn.py src/shushu/cli/_commands/explain.py tests/unit/test_cli_globals.py
git commit -m "feat(cli): learn + explain verbs"
```

---

## Task 16: `doctor` (self only)

Admin `--user` / `--all-users` variants land in Task 27 (integration). For now: check the invoker's own store.

**Files:**
- Modify: `src/shushu/cli/_commands/doctor.py`
- Create: `tests/unit/test_cli_doctor.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_doctor.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_doctor_empty_store_reports_pass():
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["summary"]["fail"] == 0


def test_doctor_reports_warn_on_empty_purpose():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    checks = payload["checks"]
    assert any(c["name"] == "purpose" and c["status"] == "WARN" for c in checks), checks


def test_doctor_reports_warn_on_expired_alert():
    store.set_secret(
        name="OLD", value="v", hidden=False, source="localhost", purpose="x",
        rotation_howto="rotate",
    )
    # backdate alert
    store.update_metadata(name="OLD", alert_at=__import__("datetime").date(1990, 1, 1))
    rc, out, _ = _run(["doctor", "--json"])
    payload = json.loads(out)
    assert any(c["name"] == "alert_at" and c["status"] == "WARN" for c in payload["checks"])
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_doctor.py -v
```

- [ ] **Step 3: Implement `doctor.py`**

Replace `src/shushu/cli/_commands/doctor.py` with:

```python
"""`shushu doctor` — store / permission / schema integrity."""

from __future__ import annotations

import os
import stat as stat_

from shushu import alerts, fs, store
from shushu.cli._errors import EXIT_STATE, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    json_mode = args.json
    # Admin variants (--user / --all-users) are wired in Task 27.
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            66,
            "doctor --user / --all-users not yet implemented",
            "coming in Task 27",
        )
    report = _run_self_checks()
    payload = {"checks": report, "summary": _summarize(report)}
    if json_mode:
        emit_result(payload, json_mode=True)
    else:
        for c in report:
            print(f"[{c['status']}] {c['name']}: {c['detail']}")
        s = payload["summary"]
        print(f"pass={s['pass']} warn={s['warn']} fail={s['fail']}")
    return 0 if payload["summary"]["fail"] == 0 else EXIT_STATE


def _run_self_checks():
    paths = fs.user_store_paths()
    checks = []

    # 1. store dir
    if not paths.dir.exists():
        checks.append({"name": "store_dir", "status": "PASS", "detail": "no store yet (lazy init)"})
    else:
        mode = stat_.S_IMODE(paths.dir.stat().st_mode)
        if mode != 0o700:
            checks.append({
                "name": "store_dir_mode", "status": "WARN",
                "detail": f"{paths.dir} mode {oct(mode)}; expected 0o700",
            })
        else:
            checks.append({"name": "store_dir", "status": "PASS", "detail": str(paths.dir)})

    # 2. file + schema
    if paths.file.exists():
        mode = stat_.S_IMODE(paths.file.stat().st_mode)
        if mode != 0o600:
            checks.append({
                "name": "secrets_file_mode", "status": "WARN",
                "detail": f"{paths.file} mode {oct(mode)}; expected 0o600",
            })
        try:
            data = store.load()
            checks.append({"name": "schema_version", "status": "PASS", "detail": f"v{data.schema_version}"})
        except store.StateError as exc:
            checks.append({"name": "schema_version", "status": "FAIL", "detail": str(exc)})
            return checks
    else:
        data = store.StoreData(schema_version=1, secrets=[])
        checks.append({"name": "schema_version", "status": "PASS", "detail": "empty store"})

    # 3. per-record checks
    for r in data.secrets:
        if not r.purpose:
            checks.append({
                "name": "purpose", "status": "WARN",
                "detail": f"{r.name} has empty purpose; consider `shushu set {r.name} --purpose '...'`",
            })
        if not r.rotation_howto:
            checks.append({
                "name": "rotation_howto", "status": "WARN",
                "detail": f"{r.name} has empty rotation_howto; consider `shushu set {r.name} --rotate-howto '...'`",
            })
        state = alerts.classify(r.alert_at)
        if state == "expired":
            checks.append({
                "name": "alert_at", "status": "WARN",
                "detail": f"{r.name} alert_at={r.alert_at} is expired",
            })
        elif state == "alerting":
            checks.append({
                "name": "alert_at", "status": "WARN",
                "detail": f"{r.name} alert_at={r.alert_at} is within 30 days",
            })
    return checks


def _summarize(checks):
    return {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "warn": sum(1 for c in checks if c["status"] == "WARN"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_doctor.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/doctor.py tests/unit/test_cli_doctor.py
git commit -m "feat(cli): doctor (self-mode) with pass/warn/fail checks"
```

---

## Task 17: `overview` (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/overview.py`
- Create: `tests/unit/test_cli_overview.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_overview.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import date

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_overview_json_includes_metadata_but_not_value():
    store.set_secret(name="FOO", value="secret123", hidden=False, source="localhost", purpose="t")
    rc, out = _run(["overview", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    rec = payload["secrets"][0]
    assert rec["name"] == "FOO"
    assert "value" not in rec
    assert "secret123" not in out


def test_overview_expired_filter():
    store.set_secret(name="A", value="v", hidden=False, source="localhost", purpose="x")
    store.set_secret(name="B", value="v", hidden=False, source="localhost", purpose="x")
    store.update_metadata(name="A", alert_at=date(1990, 1, 1))
    rc, out = _run(["overview", "--expired", "--json"])
    payload = json.loads(out)
    names = {r["name"] for r in payload["secrets"]}
    assert names == {"A"}


def test_overview_text_form_shows_alert_markers():
    store.set_secret(name="A", value="v", hidden=False, source="localhost", purpose="x")
    store.update_metadata(name="A", alert_at=date(1990, 1, 1))
    rc, out = _run(["overview"])
    assert rc == 0
    assert "A" in out
    assert "expired" in out.lower()
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_overview.py -v
```

- [ ] **Step 3: Implement `overview.py`**

Replace `src/shushu/cli/_commands/overview.py` with:

```python
"""`shushu overview` — rich metadata snapshot with alert classification."""

from __future__ import annotations

from shushu import alerts, store
from shushu.cli._errors import ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            66,
            "overview --user / --all-users not yet implemented",
            "coming in Task 27",
        )
    data = store.load()
    records = []
    for r in data.secrets:
        state = alerts.classify(r.alert_at)
        if args.expired and state != "expired":
            continue
        records.append({
            "name": r.name,
            "hidden": r.hidden,
            "source": r.source,
            "purpose": r.purpose,
            "rotation_howto": r.rotation_howto,
            "alert_at": r.alert_at.isoformat() if r.alert_at else None,
            "alert_state": state,
            "handed_over_by": r.handed_over_by,
            "created_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": r.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    if args.json:
        emit_result({"secrets": records}, json_mode=True)
    else:
        if not records:
            print("(no secrets)")
        for r in records:
            flags = []
            if r["hidden"]:
                flags.append("hidden")
            if r["alert_state"] != "ok":
                flags.append(r["alert_state"])
            tag = f"  [{','.join(flags)}]" if flags else ""
            print(f"{r['name']}{tag}  source={r['source']}  purpose={r['purpose']!r}")
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_overview.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/overview.py tests/unit/test_cli_overview.py
git commit -m "feat(cli): overview (self-mode) with alert classification"
```

---

## Task 18: `set` (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/set.py`
- Create: `tests/unit/test_cli_set.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_set.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv, stdin_text=""):
    out, err = io.StringIO(), io.StringIO()
    import sys
    with redirect_stdout(out), redirect_stderr(err):
        orig = sys.stdin
        sys.stdin = io.StringIO(stdin_text)
        try:
            rc = main(argv)
        finally:
            sys.stdin = orig
    return rc, out.getvalue(), err.getvalue()


def test_set_with_value_creates_record():
    rc, _, _ = _run(["set", "FOO", "hunter2", "--purpose", "x"])
    assert rc == 0
    assert store.get_value("FOO") == "hunter2"


def test_set_with_stdin_dash_reads_value():
    rc, _, _ = _run(["set", "FOO", "-"], stdin_text="from-stdin\n")
    assert rc == 0
    # trailing newline stripped
    assert store.get_value("FOO") == "from-stdin"


def test_set_without_value_updates_metadata_only():
    store.set_secret(name="FOO", value="orig", hidden=False, source="localhost", purpose="a")
    rc, _, _ = _run(["set", "FOO", "--purpose", "b"])
    assert rc == 0
    assert store.get_value("FOO") == "orig"
    assert store.get_record("FOO").purpose == "b"


def test_set_rejects_changing_source():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, _, err = _run(["set", "FOO", "v2", "--source", "https://other"])
    assert rc == 64
    assert "source is immutable" in err


def test_set_rejects_admin_source_prefix_without_sudo(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    rc, _, err = _run(["set", "FOO", "v", "--source", "admin:ori"])
    assert rc == 64
    assert "admin:" in err


def test_set_rejects_lowercase_name():
    rc, _, err = _run(["set", "lowercase", "v"])
    assert rc == 64


def test_set_with_alert_at_valid_date():
    rc, _, _ = _run(["set", "FOO", "v", "--alert-at", "2030-01-01"])
    assert rc == 0


def test_set_rejects_invalid_alert_at():
    rc, _, err = _run(["set", "FOO", "v", "--alert-at", "2030-13-40"])
    assert rc == 64
    assert "date" in err.lower()


def test_set_admin_user_without_sudo_is_privilege_error(monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    rc, _, err = _run(["set", "--user", "alice", "FOO", "v"])
    assert rc == 66
    assert "sudo" in err
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_set.py -v
```

- [ ] **Step 3: Implement `set.py`**

Replace `src/shushu/cli/_commands/set.py` with:

```python
"""`shushu set NAME [value] [flags]`.

With value: create or update (value + metadata).
Without value: update mutable metadata only.
"""

from __future__ import annotations

import sys

from shushu import alerts, privilege, store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        privilege.require_root(_rebuild_admin_tail(args))
        raise ShushuError(
            66,
            "set --user not yet implemented",
            "coming in Task 26 (integration task)",
        )

    # Parse alert_at eagerly for clear error.
    try:
        alert_at = alerts.parse_date(args.alert_at)
    except ValueError:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"invalid ISO date: {args.alert_at!r}",
            "use YYYY-MM-DD (e.g. 2026-10-01)",
        )

    # Reject admin:* source from unprivileged callers.
    if args.source and args.source.startswith("admin:"):
        raise ShushuError(
            EXIT_USER_ERROR,
            f"source {args.source!r} is reserved for sudo handoff",
            "drop the --source flag (shushu will default to 'localhost')",
        )

    value_given = args.value is not None
    if value_given:
        value = _read_value(args.value)
        try:
            existing = store.get_record(args.name)
            existed = True
        except store.NotFoundError:
            existed = False

        if existed:
            # Overwrite: keep source/hidden; refuse attempts to change them.
            if args.source is not None and args.source != existing.source:
                raise ShushuError(
                    EXIT_USER_ERROR,
                    "source is immutable post-create",
                    "delete and re-create to change",
                )
            if args.hidden and not existing.hidden:
                raise ShushuError(
                    EXIT_USER_ERROR,
                    "hidden is immutable post-create",
                    "delete and re-create to change",
                )
            rec = store.set_secret(
                name=args.name, value=value, hidden=existing.hidden, source=existing.source,
                purpose=args.purpose or existing.purpose,
                rotation_howto=args.rotate_howto or existing.rotation_howto,
                alert_at=alert_at if alert_at is not None else existing.alert_at,
                handed_over_by=existing.handed_over_by,
            )
        else:
            rec = store.set_secret(
                name=args.name, value=value, hidden=args.hidden,
                source=args.source or "localhost",
                purpose=args.purpose or "",
                rotation_howto=args.rotate_howto or "",
                alert_at=alert_at,
                handed_over_by=None,
            )
        _emit_ok(rec, args.json)
        return 0

    # Metadata-only update.
    try:
        rec = store.update_metadata(
            name=args.name,
            purpose=args.purpose,
            rotation_howto=args.rotate_howto,
            alert_at=alert_at,
        )
    except store.NotFoundError as exc:
        raise ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu list")
    except store.ValidationError as exc:
        raise ShushuError(EXIT_USER_ERROR, str(exc), "use `shushu delete` + re-create to change immutables")
    _emit_ok(rec, args.json)
    return 0


def _read_value(v: str) -> str:
    if v == "-":
        return sys.stdin.read().rstrip("\n")
    return v


def _rebuild_admin_tail(args) -> str:
    parts = ["set", "--user", args.user, args.name]
    if args.value is not None:
        parts.append(args.value)
    return " ".join(parts)


def _emit_ok(rec, json_mode: bool) -> None:
    if json_mode:
        emit_result({"name": rec.name, "hidden": rec.hidden, "updated_at": rec.updated_at.isoformat()}, json_mode=True)
    else:
        print(f"shushu: set {rec.name}")
```

- [ ] **Step 4: Update `_errors.py` translation** — ensure `store.ValidationError` and `store.NotFoundError` are converted to `ShushuError` at dispatch time.

Modify `src/shushu/cli/__init__.py` — inside the `try`/`except` block in `main()`, catch `store.StoreError` subclasses and wrap:

```python
    try:
        return _dispatch(args)
    except ShushuError as exc:
        _output.emit_error(exc, json_mode=json_mode)
        return exc.code
    except store.ValidationError as exc:
        _output.emit_error(ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu explain set"), json_mode=json_mode)
        return EXIT_USER_ERROR
    except store.NotFoundError as exc:
        _output.emit_error(ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu list"), json_mode=json_mode)
        return EXIT_USER_ERROR
    except store.HiddenError as exc:
        _output.emit_error(ShushuError(EXIT_USER_ERROR, str(exc), "see: shushu run --inject"), json_mode=json_mode)
        return EXIT_USER_ERROR
    except store.StateError as exc:
        _output.emit_error(ShushuError(EXIT_STATE, str(exc), "check your ~/.local/share/shushu/ for corruption"), json_mode=json_mode)
        return EXIT_STATE
    except privilege.PrivilegeError as exc:
        _output.emit_error(ShushuError(EXIT_PRIVILEGE, exc.message, exc.remediation), json_mode=json_mode)
        return EXIT_PRIVILEGE
    except NotImplementedError as exc:
        …  # (existing branch)
```

Add the missing imports at the top of the file:

```python
from shushu import privilege, store
from shushu.cli._errors import (
    EXIT_INTERNAL, EXIT_PRIVILEGE, EXIT_STATE, EXIT_SUCCESS, EXIT_USER_ERROR, ShushuError,
)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_cli_set.py tests/unit/test_cli_globals.py tests/unit/test_cli_doctor.py tests/unit/test_cli_overview.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/shushu/cli/_commands/set.py src/shushu/cli/__init__.py tests/unit/test_cli_set.py
git commit -m "feat(cli): set (self-mode) with stdin input, metadata update, immutable guards"
```

---

## Task 19: `generate` command (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/generate.py`
- Create: `tests/unit/test_cli_generate.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_generate.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_generate_hex_default_prints_value_once():
    rc, out = _run(["generate", "FOO"])
    assert rc == 0
    # 32 bytes → 64 hex chars
    printed = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
    assert any(len(line) == 64 for line in printed)
    assert store.get_value("FOO")  # stored


def test_generate_hidden_does_not_print_value():
    rc, out = _run(["generate", "SECRET", "--hidden"])
    assert rc == 0
    rec = store.get_record("SECRET")
    # The plaintext must NOT appear in stdout.
    assert rec.value not in out
    assert rec.hidden is True


def test_generate_base64_stores_correctly():
    rc, _ = _run(["generate", "FOO", "--encoding", "base64", "--bytes", "16"])
    assert rc == 0
    import base64
    decoded = base64.b64decode(store.get_value("FOO"))
    assert len(decoded) == 16


def test_generate_json_output_never_includes_value_for_hidden():
    rc, out = _run(["generate", "SECRET", "--hidden", "--json"])
    payload = json.loads(out)
    assert "value" not in payload
    assert payload["hidden"] is True
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_generate.py -v
```

- [ ] **Step 3: Implement `generate.py`**

Replace `src/shushu/cli/_commands/generate.py` with:

```python
"""`shushu generate NAME [flags]` — random secret."""

from __future__ import annotations

from shushu import alerts, generate as gen, privilege, store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        privilege.require_root(f"generate --user {args.user} {args.name}")
        raise ShushuError(66, "generate --user not yet implemented", "coming in Task 26")

    if args.source and args.source.startswith("admin:"):
        raise ShushuError(
            EXIT_USER_ERROR,
            f"source {args.source!r} is reserved for sudo handoff",
            "drop the --source flag",
        )
    try:
        alert_at = alerts.parse_date(args.alert_at)
    except ValueError:
        raise ShushuError(EXIT_USER_ERROR, f"invalid date: {args.alert_at!r}", "use YYYY-MM-DD")
    try:
        value = gen.random_secret(nbytes=args.nbytes, encoding=args.encoding)
    except ValueError as exc:
        raise ShushuError(EXIT_USER_ERROR, str(exc), "use positive --bytes and --encoding hex|base64")

    rec = store.set_secret(
        name=args.name, value=value, hidden=args.hidden,
        source=args.source or "localhost",
        purpose=args.purpose or "",
        rotation_howto=args.rotate_howto or "",
        alert_at=alert_at,
        handed_over_by=None,
    )
    if args.json:
        payload = {"name": rec.name, "hidden": rec.hidden, "encoding": args.encoding, "bytes": args.nbytes}
        if not rec.hidden:
            payload["value"] = rec.value
        emit_result(payload, json_mode=True)
    else:
        if rec.hidden:
            print(f"shushu: generated {rec.name} (hidden, {args.nbytes} bytes {args.encoding})")
        else:
            print(f"shushu: generated {rec.name} ({args.nbytes} bytes {args.encoding})")
            print(rec.value)
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_generate.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/generate.py tests/unit/test_cli_generate.py
git commit -m "feat(cli): generate (self-mode) with hidden / hex / base64"
```

---

## Task 20: `show` (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/show.py`
- Create: `tests/unit/test_cli_show.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_show.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_show_json_omits_value():
    store.set_secret(name="FOO", value="sensitive", hidden=False, source="localhost", purpose="p")
    rc, out = _run(["show", "FOO", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert "value" not in payload
    assert "sensitive" not in out
    assert payload["name"] == "FOO"


def test_show_missing_is_user_error():
    rc, _ = _run(["show", "NOPE"])
    assert rc == 64
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_show.py -v
```

- [ ] **Step 3: Implement `show.py`**

Replace `src/shushu/cli/_commands/show.py` with:

```python
"""`shushu show NAME` — metadata record (never value)."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if args.user is not None:
        raise ShushuError(66, "show --user not yet implemented", "coming in Task 26")
    rec = store.get_record(args.name)  # NotFoundError caught by main()
    payload = {
        "name": rec.name,
        "hidden": rec.hidden,
        "source": rec.source,
        "purpose": rec.purpose,
        "rotation_howto": rec.rotation_howto,
        "alert_at": rec.alert_at.isoformat() if rec.alert_at else None,
        "handed_over_by": rec.handed_over_by,
        "created_at": rec.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": rec.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.json:
        emit_result(payload, json_mode=True)
    else:
        for k, v in payload.items():
            print(f"{k}: {v}")
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_show.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/show.py tests/unit/test_cli_show.py
git commit -m "feat(cli): show (metadata-only, never value)"
```

---

## Task 21: `get`

**Files:**
- Modify: `src/shushu/cli/_commands/get.py`
- Create: `tests/unit/test_cli_get.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_get.py`:

```python
from __future__ import annotations

import io
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_get_visible_prints_value():
    store.set_secret(name="FOO", value="bar", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["get", "FOO"])
    assert rc == 0
    assert out.strip() == "bar"


def test_get_hidden_refuses_with_remediation():
    store.set_secret(name="SECRET", value="s", hidden=True, source="localhost", purpose="")
    rc, _, err = _run(["get", "SECRET"])
    assert rc == 64
    assert "hidden" in err.lower()
    assert "inject" in err.lower()


def test_get_missing_is_user_error():
    rc, _, err = _run(["get", "NOPE"])
    assert rc == 64
    assert "NOPE" in err


def test_get_does_not_accept_user_flag():
    # argparse rejects unknown flags with exit 2.
    rc, _, _ = _run(["get", "FOO", "--user", "alice"])
    assert rc == 2
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_get.py -v
```

- [ ] **Step 3: Implement `get.py`**

Replace `src/shushu/cli/_commands/get.py` with:

```python
"""`shushu get NAME` — print value (refuses hidden)."""

from __future__ import annotations

from shushu import store
from shushu.cli._output import emit_result


def handle(args) -> int:
    value = store.get_value(args.name)  # HiddenError/NotFoundError caught by main()
    if args.json:
        emit_result({"name": args.name, "value": value}, json_mode=True)
    else:
        print(value)
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_get.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/get.py tests/unit/test_cli_get.py
git commit -m "feat(cli): get (with hidden-refusal)"
```

---

## Task 22: `env`

**Files:**
- Modify: `src/shushu/cli/_commands/env.py`
- Create: `tests/unit/test_cli_env.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_env.py`:

```python
from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_env_emits_single_quoted_exports():
    store.set_secret(name="FOO", value="hello", hidden=False, source="localhost", purpose="")
    store.set_secret(name="BAR", value="world", hidden=False, source="localhost", purpose="")
    rc, out, _ = _run(["env", "FOO", "BAR"])
    assert rc == 0
    assert "export FOO='hello'" in out
    assert "export BAR='world'" in out


def test_env_escapes_single_quotes_posix_safe():
    store.set_secret(
        name="TRICKY", value="it's \"quoted\" and 'risky'",
        hidden=False, source="localhost", purpose="",
    )
    rc, out, _ = _run(["env", "TRICKY"])
    assert rc == 0
    # Round-trip through bash.
    result = subprocess.run(
        ["bash", "-c", f"{out.strip()}; printf %s \"$TRICKY\""],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout == "it's \"quoted\" and 'risky'"


def test_env_refuses_when_any_name_is_hidden():
    store.set_secret(name="VIS", value="v", hidden=False, source="localhost", purpose="")
    store.set_secret(name="HID", value="h", hidden=True, source="localhost", purpose="")
    rc, _, err = _run(["env", "VIS", "HID"])
    assert rc == 64
    assert "HID" in err


def test_env_missing_name_is_user_error():
    rc, _, err = _run(["env", "NOPE"])
    assert rc == 64
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_env.py -v
```

- [ ] **Step 3: Implement `env.py`**

Replace `src/shushu/cli/_commands/env.py` with:

```python
"""`shushu env NAME1 [NAME2 ...]` — emit POSIX shell export lines."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError


def handle(args) -> int:
    records = []
    for name in args.names:
        rec = store.get_record(name)  # NotFoundError caught by main()
        if rec.hidden:
            raise ShushuError(
                EXIT_USER_ERROR,
                f"{name} is hidden",
                f"exclude it or use `shushu run --inject {name}={name} -- <cmd>`",
            )
        records.append(rec)
    for rec in records:
        print(f"export {rec.name}='{_posix_quote(rec.value)}'")
    return 0


def _posix_quote(value: str) -> str:
    """POSIX single-quote-safe: replace embedded ' with '\\''."""
    return value.replace("'", "'\\''")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_env.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/env.py tests/unit/test_cli_env.py
git commit -m "feat(cli): env (POSIX-quoted exports, hidden-refusal)"
```

---

## Task 23: `run --inject`

**Files:**
- Modify: `src/shushu/cli/_commands/run.py`
- Create: `tests/unit/test_cli_run.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_run.py`:

```python
from __future__ import annotations

import io
import os
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_run_parses_inject_spec_visible_secret(tmp_path):
    store.set_secret(name="VIS", value="hello", hidden=False, source="localhost", purpose="")
    # Use subprocess to actually exec (runs in a child process so os.execvp doesn't kill the test).
    out = subprocess.run(
        [sys.executable, "-m", "shushu", "run", "--inject", "X=VIS", "--",
         sys.executable, "-c", "import os; print(os.environ['X'])"],
        capture_output=True, text=True, env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "hello"


def test_run_hidden_secret_injects_ok(tmp_path):
    store.set_secret(name="HID", value="secret", hidden=True, source="localhost", purpose="")
    out = subprocess.run(
        [sys.executable, "-m", "shushu", "run", "--inject", "Y=HID", "--",
         sys.executable, "-c", "import os; print(os.environ['Y'])"],
        capture_output=True, text=True, env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "secret"


def test_run_malformed_inject_is_user_error():
    rc, _, err = _run(["run", "--inject", "=NAME", "--", "/bin/true"])
    assert rc == 64
    assert "VAR=NAME" in err


def test_run_missing_secret_is_user_error():
    rc, _, err = _run(["run", "--inject", "X=NOPE", "--", "/bin/true"])
    assert rc == 64


def test_run_requires_double_dash_before_cmd():
    rc, _, _ = _run(["run", "--inject", "X=VIS"])  # no cmd
    assert rc == 64


def test_run_duplicate_var_last_wins(capsys, monkeypatch):
    store.set_secret(name="A", value="one", hidden=False, source="localhost", purpose="")
    store.set_secret(name="B", value="two", hidden=False, source="localhost", purpose="")
    out = subprocess.run(
        [sys.executable, "-m", "shushu", "run", "--inject", "X=A", "--inject", "X=B", "--",
         sys.executable, "-c", "import os; print(os.environ['X'])"],
        capture_output=True, text=True,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "two"
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_run.py -v
```

- [ ] **Step 3: Implement `run.py`**

Replace `src/shushu/cli/_commands/run.py` with:

```python
"""`shushu run --inject VAR=NAME ... -- cmd [args]` — exec with env."""

from __future__ import annotations

import os
import sys

from shushu import store
from shushu.cli._errors import EXIT_USER_ERROR, ShushuError


def handle(args) -> int:
    cmd_and_args = args.cmd_and_args or []
    if not cmd_and_args:
        raise ShushuError(
            EXIT_USER_ERROR,
            "no command given after --",
            "expected form: shushu run --inject VAR=NAME -- <cmd> [args...]",
        )
    # argparse.REMAINDER leaves a leading '--' if the user included one.
    if cmd_and_args[0] == "--":
        cmd_and_args = cmd_and_args[1:]
    if not cmd_and_args:
        raise ShushuError(EXIT_USER_ERROR, "no command given after --", "expected form: shushu run --inject VAR=NAME -- <cmd>")

    env_add: dict[str, str] = {}
    for spec in args.inject:
        var, name = _parse_inject(spec)
        rec = store.get_record(name)  # NotFoundError caught by main()
        env_add[var] = rec.value  # last-wins on duplicate var

    new_env = {**os.environ, **env_add}
    try:
        os.execvpe(cmd_and_args[0], cmd_and_args, new_env)
    except FileNotFoundError:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"command not found: {cmd_and_args[0]!r}",
            "check PATH or use an absolute path",
        )
    return 0  # unreachable — execvpe replaces the process


def _parse_inject(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: missing '='",
            "expected form: VAR=NAME (e.g. --inject OPENAI_API_KEY=OPENAI_API_KEY)",
        )
    var, _, name = spec.partition("=")
    if not var:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: empty variable name",
            "expected form: VAR=NAME",
        )
    if not name:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"malformed --inject {spec!r}: empty secret name",
            "expected form: VAR=NAME",
        )
    return var, name
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_run.py -v
```

Note: the subprocess-based tests require `shushu` to be importable (`python -m shushu`) — confirm `src/shushu/__main__.py` still exists and calls `main()`. If not, ensure it reads:

```python
from shushu.cli import main
import sys
raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/run.py src/shushu/__main__.py tests/unit/test_cli_run.py
git commit -m "feat(cli): run --inject exec (last-wins on dup var, explicit malform errors)"
```

---

## Task 24: `list` (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/list_.py`
- Create: `tests/unit/test_cli_list.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_list.py`:

```python
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_list_empty_prints_nothing_text():
    rc, out = _run(["list"])
    assert rc == 0
    assert out == ""


def test_list_names_sorted_one_per_line():
    for n in ["C", "A", "B"]:
        store.set_secret(name=n, value="v", hidden=False, source="localhost", purpose="")
    rc, out = _run(["list"])
    assert rc == 0
    assert out.splitlines() == ["A", "B", "C"]


def test_list_json():
    store.set_secret(name="X", value="v", hidden=False, source="localhost", purpose="")
    rc, out = _run(["list", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload == {"ok": True, "names": ["X"]}
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_list.py -v
```

- [ ] **Step 3: Implement `list_.py`**

Replace `src/shushu/cli/_commands/list_.py` with:

```python
"""`shushu list` — names only, one per line."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(66, "list --user / --all-users not yet implemented", "coming in Task 26")
    names = store.list_names()
    if args.json:
        emit_result({"names": names}, json_mode=True)
    else:
        for n in names:
            print(n)
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_list.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/list_.py tests/unit/test_cli_list.py
git commit -m "feat(cli): list (names only, one per line)"
```

---

## Task 25: `delete` (self only)

**Files:**
- Modify: `src/shushu/cli/_commands/delete.py`
- Create: `tests/unit/test_cli_delete.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_delete.py`:

```python
from __future__ import annotations

import io
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu import store
from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_delete_removes_record():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    rc, _, _ = _run(["delete", "FOO"])
    assert rc == 0
    assert store.list_names() == []


def test_delete_missing_is_user_error():
    rc, _, err = _run(["delete", "NOPE"])
    assert rc == 64
    assert "NOPE" in err
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
uv run pytest tests/unit/test_cli_delete.py -v
```

- [ ] **Step 3: Implement `delete.py`**

Replace `src/shushu/cli/_commands/delete.py` with:

```python
"""`shushu delete NAME` — remove a secret."""

from __future__ import annotations

from shushu import store
from shushu.cli._errors import ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    if getattr(args, "user", None):
        raise ShushuError(66, "delete --user not yet implemented", "coming in Task 26")
    store.delete(args.name)  # NotFoundError caught by main()
    if args.json:
        emit_result({"name": args.name, "deleted": True}, json_mode=True)
    else:
        print(f"shushu: deleted {args.name}")
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli_delete.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/shushu/cli/_commands/delete.py tests/unit/test_cli_delete.py
git commit -m "feat(cli): delete"
```

---

## Task 26: Admin mode — `--user` / `--all-users` for all relevant verbs

Wires up admin handoff using `privilege.run_as_user`. Adds read-only `--all-users` for `list`, `overview`, `doctor`. Adds write `--user` for `set`, `generate`, `show`, `list`, `delete`, `overview`, `doctor`.

**Files:**
- Modify: `src/shushu/cli/_commands/{set,generate,show,list_,delete,overview,doctor}.py`
- Create: `src/shushu/admin.py` (shared helpers)
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_admin_handoff.py`
- Create: `tests/integration/test_all_users_enumeration.py`

- [ ] **Step 1: Create `src/shushu/admin.py`**

```python
"""Admin-mode helpers: fork-as-target-user for writes, read-as-root for reads.

Used by every CLI command that accepts --user / --all-users. Keeps the
identity-switch logic out of individual command handlers.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from shushu import privilege, users
from shushu.cli._errors import EXIT_BACKEND, ShushuError


def as_user(name: str, fn: Callable[[], int]) -> int:
    """Run fn() as the target user via fork + setuid. Returns the child's exit code."""
    privilege.require_root(f"--user {name}")
    try:
        info = users.resolve(name)
    except KeyError:
        raise ShushuError(EXIT_BACKEND, f"no OS user {name!r} on this host", "check: getent passwd")
    if not info.home.exists():
        raise ShushuError(EXIT_BACKEND, f"user {name!r} has no home directory", "create one or pick a different user")
    return privilege.run_as_user(info, fn)


def for_each_user(fn: Callable[[users.UserInfo], dict[str, Any]]) -> list[dict[str, Any]]:
    """Enumerate all OS users and invoke fn per-user. Reads only — no uid switch.

    The caller must be root. Fn is responsible for skipping users with no
    shushu store.
    """
    privilege.require_root("--all-users")
    out = []
    for info in users.all_users():
        if not info.home.exists():
            continue
        if not (info.home / ".local/share/shushu/secrets.json").exists():
            continue
        row = fn(info)
        if row is not None:
            out.append(row)
    return out


def store_paths_for(info: users.UserInfo):
    """What fs.user_store_paths would return if we were this user."""
    from shushu import fs  # local import to avoid circular
    base = info.home / ".local/share/shushu"
    return fs.StorePaths(dir=base, file=base / "secrets.json", lock=base / ".lock")
```

- [ ] **Step 2: Update each command handler to route through `admin.as_user`**

Example for `set.py` — replace the `if args.user is not None:` stub branch with:

```python
    if args.user is not None:
        import os as _os
        handed_over_by = privilege.sudo_invoker()
        # Force source="admin:<invoker>" for provenance unless caller gave one.
        source = args.source or f"admin:{handed_over_by}"

        def _child() -> int:
            # Inside the child we're now the target user; SHUSHU_HOME is NOT set,
            # so fs.user_store_paths() resolves to ~/.local/share/shushu of that user.
            _os.environ.pop("SHUSHU_HOME", None)
            # Re-parse date inside child too — validation must still happen here.
            try:
                alert_at_c = alerts.parse_date(args.alert_at)
            except ValueError:
                raise ShushuError(EXIT_USER_ERROR, f"invalid date: {args.alert_at!r}", "use YYYY-MM-DD")
            value_c = _read_value(args.value) if args.value is not None else None
            if value_c is None:
                # Metadata-only update path
                store.update_metadata(
                    name=args.name, purpose=args.purpose,
                    rotation_howto=args.rotate_howto, alert_at=alert_at_c,
                )
            else:
                # Create/overwrite path. Reuse same immutability rules as self-mode.
                try:
                    existing = store.get_record(args.name)
                except store.NotFoundError:
                    existing = None
                if existing is not None:
                    store.set_secret(
                        name=args.name, value=value_c, hidden=existing.hidden,
                        source=existing.source,
                        purpose=args.purpose or existing.purpose,
                        rotation_howto=args.rotate_howto or existing.rotation_howto,
                        alert_at=alert_at_c if alert_at_c is not None else existing.alert_at,
                        handed_over_by=existing.handed_over_by,
                    )
                else:
                    store.set_secret(
                        name=args.name, value=value_c, hidden=args.hidden,
                        source=source, purpose=args.purpose or "",
                        rotation_howto=args.rotate_howto or "",
                        alert_at=alert_at_c, handed_over_by=handed_over_by,
                    )
            return 0

        from shushu import admin
        return admin.as_user(args.user, _child)
```

Apply the parallel pattern to `generate.py` (force `source = "admin:<invoker>"` if not set; propagate `handed_over_by`), `delete.py` (straight delete inside the fork), `show.py`/`list_.py`/`overview.py`/`doctor.py` (read-only — for `--user` fork, for `--all-users` use `admin.for_each_user`).

**Key invariant for read commands with `--all-users`:** iterate `admin.for_each_user`, and inside the callback, read *that user's* store by computing paths from the user's home dir (use `admin.store_paths_for(info)`). Root can read the files directly — no fork required for reads.

For conciseness, here's the pattern for `list_.py`:

```python
def handle(args) -> int:
    if args.all_users:
        from shushu import admin, fs
        def _row(info):
            paths = admin.store_paths_for(info)
            try:
                data_raw = paths.file.read_text(encoding="utf-8")
            except OSError:
                return None
            import json as _json
            names = sorted(s["name"] for s in _json.loads(data_raw).get("secrets", []))
            return {"user": info.name, "names": names}
        rows = admin.for_each_user(_row)
        if args.json:
            emit_result({"users": rows}, json_mode=True)
        else:
            for row in rows:
                print(f"# {row['user']}")
                for n in row["names"]:
                    print(n)
        return 0
    if args.user is not None:
        from shushu import admin
        def _child():
            import os as _os
            _os.environ.pop("SHUSHU_HOME", None)
            for n in store.list_names():
                print(n)
            return 0
        return admin.as_user(args.user, _child)
    # self-mode — existing body
    names = store.list_names()
    if args.json:
        emit_result({"names": names}, json_mode=True)
    else:
        for n in names:
            print(n)
    return 0
```

Apply analogous logic to `overview.py` and `doctor.py`.

- [ ] **Step 3: Write integration tests**

`tests/integration/__init__.py`: empty.

`tests/integration/test_admin_handoff.py`:

```python
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
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"),
    reason="admin handoff requires root (CI runs this inside a container)",
)


@pytest.fixture(scope="module")
def two_users():
    """Create two throwaway OS users. Destroyed at module teardown."""
    names = ["shushutest_alice", "shushutest_bob"]
    for n in names:
        subprocess.run(["useradd", "-m", n], check=True)
    yield names
    for n in names:
        subprocess.run(["userdel", "-r", n], check=False)


def _shushu(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "shushu", *args],
        capture_output=True, text=True, env=env,
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


def test_admin_generate_hidden_never_shows_value(two_users):
    _alice, bob = two_users
    r = _shushu("generate", "--user", bob, "BOBKEY", "--hidden", "--bytes", "32")
    assert r.returncode == 0, r.stderr
    target = pathlib.Path(pwd.getpwnam(bob).pw_dir) / ".local/share/shushu/secrets.json"
    payload = json.loads(target.read_text())
    actual_value = payload["secrets"][0]["value"]
    assert actual_value not in r.stdout
    assert actual_value not in r.stderr


def test_target_user_can_inspect_not_admin_field(two_users):
    alice, _ = two_users
    _shushu("set", "--user", alice, "FOO", "v")
    # Now drop to alice and run show.
    r = subprocess.run(
        ["sudo", "-u", alice, sys.executable, "-m", "shushu", "show", "FOO", "--json"],
        capture_output=True, text=True,
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
            assert path.stat().st_uid != 0, f"root-owned leak at {path}"
```

`tests/integration/test_all_users_enumeration.py`:

```python
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"),
    reason="requires root",
)


def test_overview_all_users_never_exposes_value(tmp_path):
    # Create a user, write a secret as them, then run overview --all-users as root.
    name = "shushutest_carol"
    subprocess.run(["useradd", "-m", name], check=True)
    try:
        subprocess.run(
            ["sudo", "-u", name, sys.executable, "-m", "shushu", "set", "SEC", "supersecret"],
            check=True,
        )
        r = subprocess.run(
            [sys.executable, "-m", "shushu", "overview", "--all-users", "--json"],
            capture_output=True, text=True, check=True,
        )
        assert "supersecret" not in r.stdout
        payload = json.loads(r.stdout)
        assert payload["ok"] is True
        # Find our test user's row.
        users_rows = payload.get("users", [])
        found = [row for row in users_rows if row.get("user") == name]
        assert found, users_rows
    finally:
        subprocess.run(["userdel", "-r", name], check=False)
```

- [ ] **Step 4: Run the unit tests locally (integration skipped unless root)**

```bash
uv run pytest tests/unit -v
```

Expected: all pass; the admin paths for `set`/`generate`/etc. are exercised in integration, which is skipped unless root.

- [ ] **Step 5: Run the integration tests inside the Docker image**

```bash
docker build -f .github/workflows/Dockerfile.integration -t shushu-int .
docker run --rm shushu-int uv run pytest tests/integration -v
```

Expected: all integration tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/shushu/admin.py src/shushu/cli/_commands/ tests/integration/
git commit -m "feat(admin): --user / --all-users via setuid-fork; integration tests"
```

---

## Task 27: Self-verify acceptance gate

Replaces the scaffold's `tests/test_self_verify.py` with the 13-step lifecycle from the spec.

**Files:**
- Create (or replace): `tests/test_self_verify.py`

- [ ] **Step 1: Write the lifecycle test**

Full contents of `tests/test_self_verify.py`:

```python
"""End-to-end dogfood lifecycle. Every regression here blocks the commit."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from shushu.cli import main


@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_self_verify_lifecycle(tmp_path):
    # 1. set
    assert _run(["set", "FOO", "bar", "--purpose", "self-test", "--alert-at", "2099-01-01"])[0] == 0
    # 2. generate hidden
    rc, out_gen, _ = _run(["generate", "BAZ", "--bytes", "16", "--hidden"])
    assert rc == 0
    # The hidden value must not appear.
    # (The literal value is random; we assert structure.)
    assert "BAZ" in out_gen
    # 3. list
    rc, out, _ = _run(["list", "--json"])
    payload = json.loads(out)
    assert set(payload["names"]) == {"FOO", "BAZ"}
    # 4. show
    rc, out, _ = _run(["show", "FOO", "--json"])
    assert json.loads(out).get("value") is None  # no value key at all
    # 5. get
    rc, out, _ = _run(["get", "FOO"])
    assert out.strip() == "bar"
    # 6. get hidden → refused
    rc, _, err = _run(["get", "BAZ"])
    assert rc == 64
    # 7. env
    rc, out, _ = _run(["env", "FOO"])
    assert "export FOO='bar'" in out
    # 8. run --inject via subprocess (real execvp)
    r = subprocess.run(
        [sys.executable, "-m", "shushu", "run", "--inject", "X=BAZ", "--",
         sys.executable, "-c", "import os; print(len(os.environ['X']))"],
        capture_output=True, text=True,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "32"  # 16 bytes hex = 32 chars
    # 9. metadata-only set
    assert _run(["set", "FOO", "--purpose", "updated"])[0] == 0
    # 10. immutable refusal
    rc, _, _ = _run(["set", "FOO", "v2", "--source", "https://other"])
    assert rc == 64
    # 11. delete
    assert _run(["delete", "FOO"])[0] == 0
    # 12. doctor
    rc, out, _ = _run(["doctor", "--json"])
    assert json.loads(out)["ok"] is True
    # 13. overview — 1 remaining
    rc, out, _ = _run(["overview", "--json"])
    assert len(json.loads(out)["secrets"]) == 1
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/test_self_verify.py -v
```

Expected: passes end-to-end.

- [ ] **Step 3: Delete the old scaffold version test if it still exists**

The scaffold had a `test_default_prints_version` test; Task 1 replaced it. Confirm nothing stale remains:

```bash
grep -rn "test_default_prints_version" tests/ || echo "clean"
```

Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_self_verify.py
git commit -m "test: full-lifecycle self-verify acceptance gate"
```

---

## Task 28: Flesh out docs + README + CLAUDE.md

**Files:**
- Rewrite: `README.md`
- Modify: `CLAUDE.md`
- Flesh out: `docs/threat-model.md`, `docs/testing.md`, `docs/rubric-mapping.md`

- [ ] **Step 1: Rewrite `README.md`**

Replace the scaffold README with a complete description. Minimum sections:

```markdown
# shushu

Agent-first per-OS-user secrets manager CLI. Part of the
[AgentCulture](https://github.com/agentculture) ecosystem; sibling to
[`zehut`](https://github.com/agentculture/zehut) (identity) and patterned
on [`afi-cli`](https://github.com/agentculture/afi-cli).

## Install

```bash
uv tool install shushu
shushu --version
```

## Quick start

```bash
# store a secret you already have
shushu set OPENAI_API_KEY sk-...

# generate a random one
shushu generate JWT_SECRET --bytes 32 --hidden

# inspect (never prints value)
shushu show OPENAI_API_KEY

# consume
shushu get OPENAI_API_KEY
eval $(shushu env OPENAI_API_KEY)
shushu run --inject JWT=JWT_SECRET -- ./myapp
```

## Admin handoff

```bash
# as root: provision a secret into alice's store
sudo shushu set --user alice OPENAI_API_KEY sk-...

# read-only audit across all users
sudo shushu overview --all-users
```

## Docs

- [Design spec](docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md)
- [Threat model](docs/threat-model.md)
- [Testing notes](docs/testing.md)
- [afi-rubric mapping](docs/rubric-mapping.md)

## License

MIT. © 2026 Ori Nachum / AgentCulture.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Rewrite the existing `CLAUDE.md` to match the post-v1 shape (mirroring zehut's post-v1 CLAUDE). Minimum:

- Project status → `shushu v0.1.0 — agent-first per-OS-user secrets manager`.
- Layout section → updated to reflect `src/shushu/cli/` package + all new modules.
- Common commands → include `shushu set/generate/get/env/run/…`.
- Version discipline → reference `.claude/skills/version-bump/scripts/bump.py`.
- Python version → `>= 3.12`.

- [ ] **Step 3: Flesh out `docs/threat-model.md`**

Expand the stub into a full document using the spec's §8 as the source (copy the full prose with minor reformatting). End with a "Residual risks" table including the **encryption-at-rest** row with a link to the issue that will be filed in Task 29.

- [ ] **Step 4: Flesh out `docs/testing.md`**

Document:
- `SHUSHU_HOME` env var — overrides store path; tests-only.
- `SHUSHU_DOCKER` env var — opts into integration tests outside a real root session.
- How to run unit tests: `uv run pytest tests/unit -v`.
- How to run integration tests: `docker build -f .github/workflows/Dockerfile.integration -t shushu-int . && docker run --rm shushu-int`.
- Coverage invocation: `uv run pytest --cov=shushu --cov-report=term`.

- [ ] **Step 5: Flesh out `docs/rubric-mapping.md`**

For each verb, document:
- One-line purpose.
- Exit codes it emits and why.
- JSON payload shape on success.

Example block for `get`:

```markdown
## get

Print value. Refused if hidden.

- `0` on success (value printed).
- `64` if hidden (`remediation` points at `run --inject`) or if name missing.

JSON success shape:

```json
{"ok": true, "name": "<NAME>", "value": "<VALUE>"}
```

Repeat for every verb.

- [ ] **Step 6: Lint the markdown**

```bash
scripts/lint-md.sh
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add README.md CLAUDE.md docs/
git commit -m "docs: full threat-model, testing, rubric-mapping; rewrite README + CLAUDE"
```

---

## Task 29: File the encryption-at-rest issue + final checks

**Files:** (no code changes — user-action task)

- [ ] **Step 1: File the encryption-at-rest issue**

The issue must exist before v0.1.0 is released, because the threat model references it. The plan-runner cannot do this automatically — ask the user to file it.

Suggested body to paste into `https://github.com/agentculture/shushu/issues/new`:

```markdown
**Title:** v2: encryption at rest for secret values

**Body:**

shushu v1 stores secret values in plaintext at 0600 in each user's
`~/.local/share/shushu/secrets.json`. The `hidden` flag is a CLI
contract (shushu refuses to emit values via get/env/show), not
cryptography — a user with shell access to their own home can
`cat` the file and see every hidden secret.

This is explicitly documented in the threat model
(`docs/threat-model.md` §8.3), but it means the "hidden" contract
only protects against:
- accidental copy-paste / screen-share leaks
- agents that honor the CLI surface
- backup pipelines that only see the CLI's output

It does NOT protect against:
- a malicious local process running as the same user
- a backup that copies `~/.local/share/shushu/`
- a compromised shell history

v2 should add real at-rest encryption. Candidates:

1. **age with a per-user identity file** at
   `~/.local/share/shushu/identity.key` (mode 0600). `shushu init`
   generates it; `shushu` decrypts-on-read.
2. **libsecret** (gnome-keyring / KDE wallet) via the `secretstorage`
   Python package. Good UX on desktop Linux; broken for headless
   servers / containers without a keyring daemon.
3. **pass/gpg** — defer to the user's existing gpg identity.
   Max alignment with existing secret-hygiene tooling; higher setup
   cost.

Decision in v2 should balance headless-agent usability (critical for
AgentCulture) against UX for human operators.

Acceptance criteria (v2):
- New `encrypted_at_rest: true` flag in `schema_version = 2`.
- `schema_version = 1` stores remain readable (or a migration path).
- Self-verify lifecycle still passes.
- Threat model updated; this issue closed.

Linked in threat model: docs/threat-model.md §8.4
```

Record the issue URL — the threat model should link to it. If you can, update `docs/threat-model.md` to replace the placeholder link with the real issue URL, then commit that one-liner.

- [ ] **Step 2: Full test sweep**

```bash
uv run pytest tests/unit tests/test_self_verify.py --cov=shushu --cov-report=term -v
```

Expected: all unit tests + self-verify pass. Coverage ≥ 70%, store ≥ 95%.

- [ ] **Step 3: Full integration sweep inside Docker**

```bash
docker build -f .github/workflows/Dockerfile.integration -t shushu-int .
docker run --rm shushu-int uv run pytest tests/ -v
```

Expected: everything green, including integration tests.

- [ ] **Step 4: Lint everything**

```bash
uv run black --check src tests
uv run isort --check-only src tests
uv run flake8 src tests
scripts/lint-md.sh
```

Expected: no findings.

- [ ] **Step 5: Append the CHANGELOG entry for v0.1.0**

Move the empty `[Unreleased]` block into `[0.1.0] — 2026-04-24` with a complete list of v1 features (set/generate/show/get/env/run/overview/doctor/list/delete, admin handoff, hidden contract, metadata with alert_at, etc.).

- [ ] **Step 6: Commit the changelog + issue-URL update**

```bash
git add CHANGELOG.md docs/threat-model.md
git commit -m "docs: v0.1.0 changelog + link encryption-at-rest tracking issue"
```

- [ ] **Step 7: Final sanity**

```bash
uv run shushu --version        # → shushu 0.1.0
uv run shushu learn | head
uv run shushu explain hidden
```

- [ ] **Step 8: (optional) Open the v0.1.0 PR**

If agentculture/shushu is set up with trusted publishing, open the PR:

```bash
git push -u origin scaffold-uv-cli
gh pr create --title "shushu v0.1.0 — agent-first per-OS-user secrets manager" \
  --body "$(cat <<'EOF'
## Summary

Implements the v1 CLI per `docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md`.

- 12 verbs: set, show, get, env, run, generate, list, delete, overview, doctor, learn, explain
- Per-OS-user store under ~/.local/share/shushu/ (0600)
- Hidden-secret contract (H2): consume via `shushu run --inject` only
- Admin handoff (sudo --user / --all-users) via setuid-fork
- Rich metadata: source, purpose, rotation_howto, alert_at, handed_over_by

## Test plan

- [x] unit tests pass
- [x] self-verify lifecycle passes
- [x] integration tests pass in Docker (admin handoff, all-users)
- [x] encryption-at-rest issue filed: #<ISSUE>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Plan self-review notes

Checked against the spec section-by-section:

- §1 scope → Tasks 1–29 cover every in-scope feature.
- §2 CLI surface → Tasks 15 (learn/explain), 16 (doctor), 17 (overview), 18 (set), 19 (generate), 20 (show), 21 (get), 22 (env), 23 (run), 24 (list), 25 (delete), 26 (admin dimension).
- §3 architecture → Tasks 7–12 create each module; Task 13 adds `_errors`/`_output`; Task 14 wires the parser.
- §4 storage schema → Task 12 (`store.py`) + Task 7 (`fs.py`) implement it.
- §5 error model → Task 13 + Task 18 (wraps in `main()`).
- §6 packaging/CI → Tasks 1, 4, 5.
- §7 testing → Tasks 2 (unit tests per module), 26 (integration), 27 (self-verify).
- §8 threat model → Task 28 writes the doc.
- §9 acceptance → Task 29 runs the full sweep.
- §10 open questions → 1 (UTC) in Task 8; 2 (inject malform) in Task 23; 3 (POSIX quote) in Task 22; 4 (list vs overview) in Tasks 17, 24; 5 (shutil.which) in Task 11; 6 (version test rewrite) in Task 1.
- §11 related docs → Task 28.

**Known handoff gotcha:** Task 26 is the largest task because it weaves admin mode through six command handlers. If executed as a subagent task, consider splitting it into 26a (`admin.py` + integration test scaffolding) and 26b (per-command `--user` wiring).

---

**End of plan.** See the sibling spec for authoritative design; update this plan if the spec is revised.
