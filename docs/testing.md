# shushu testing notes

(Stub — full content lands in Task 28. This page only documents the
test-isolation conventions wired into the suite today.)

## Test artifacts live under `/tmp/shushu-tests/`

`pyproject.toml` pins pytest's `--basetemp` to `/tmp/shushu-tests/`, so
every `tmp_path` / `tmp_path_factory` allocation lands under one root.
`tmp_path_retention_policy = "failed"` plus `tmp_path_retention_count = 3`
means:

- A passing test's `tmp_path` is **deleted immediately** after the test.
- The most recent **3 failed** test runs are kept for post-mortem
  inspection.

Cleanup is a single command: `rm -rf /tmp/shushu-tests/`. Or use the
wrapper:

```bash
bash .claude/skills/run-tests/scripts/test.sh --clean-only
```

See `.claude/skills/run-tests/SKILL.md` for the full wrapper interface
(`-p` parallel, `--ci` mirror, `-k` clean-after-run, etc.).

## `SHUSHU_HOME` env override

`shushu.fs.user_store_paths()` checks `SHUSHU_HOME` first, then falls
back to `~/.local/share/shushu`. Tests that need an isolated store
redirect it via `monkeypatch`:

```python
@pytest.fixture(autouse=True)
def _tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))
```

`tmp_path` is per-test, lives under `/tmp/shushu-tests/`, and the env
mutation is scoped to the test via `monkeypatch`.

## Smoke-test convention (manual / CLI)

When running ad-hoc `SHUSHU_HOME=...` smoke commands by hand from the
shell — e.g., to verify a new verb in a fresh store — use the
`/tmp/shushu-tests/smoke-<topic>/` namespace, NOT scattered top-level
paths like `/tmp/shushu-pr5` or `/tmp/shushu-task18-smoke`. Use the
run-tests wrapper to get the path and to clean up; **never write a
direct `rm -rf` against `/tmp/shushu-tests/*` by hand.**

```bash
TEST_SH=.claude/skills/run-tests/scripts/test.sh
SMOKE="$(bash $TEST_SH --smoke-home task22)"   # prints /tmp/shushu-tests/smoke-task22
bash $TEST_SH --clean-smoke task22              # safe wipe, validated name
SHUSHU_HOME="$SMOKE" uv run shushu generate KEY
SHUSHU_HOME="$SMOKE" uv run shushu generate SEKRET --hidden
bash $TEST_SH --clean-smoke task22              # always clean up after
```

The wrapper validates the namespace (rejects `..`, `/`, empty, etc.)
so you can't accidentally point the rm at a parent directory.

Cleanup discipline: every smoke session begins and ends with
`--clean-smoke <name>`. For a full reset of all smoke + pytest
artifacts at once: `bash $TEST_SH --clean-only`.

## `SHUSHU_DOCKER` integration gate

Integration tests under `tests/integration/` (added in Task 26) are
marked with the pytest `integration` marker and gated behind the
`SHUSHU_DOCKER=1` environment variable. They exercise real
`useradd` / `userdel` and the setuid-fork handoff, so they only run
in the disposable container defined by
`.github/workflows/Dockerfile.integration`.

To run integration tests locally inside the container:

```bash
docker build -f .github/workflows/Dockerfile.integration -t shushu-int .
docker run --rm -e SHUSHU_DOCKER=1 shushu-int pytest -m integration -v
```

The unit suite (default `uv run pytest`) excludes integration tests
unless `SHUSHU_DOCKER=1` is set in the host environment.
