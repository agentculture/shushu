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

Cleanup is a single command: `rm -rf /tmp/shushu-tests/`.

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
paths like `/tmp/shushu-pr5` or `/tmp/shushu-task18-smoke`. Pattern:

```bash
mkdir -p /tmp/shushu-tests
SMOKE=/tmp/shushu-tests/smoke-task19
rm -rf "$SMOKE"
SHUSHU_HOME="$SMOKE" uv run shushu generate KEY
SHUSHU_HOME="$SMOKE" uv run shushu generate SEKRET --hidden
rm -rf "$SMOKE"   # always clean up your own artifacts
```

Cleanup discipline: every smoke session begins with `rm -rf "$SMOKE"`
and ends with the same. Then `rm -rf /tmp/shushu-tests/` is always a
safe blast-radius reset for the whole project.

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
