---
name: run-tests
description: >
  Run shushu's pytest suite with optional parallelism, coverage, and
  one-shot cleanup of /tmp/shushu-tests/. Use when running tests,
  verifying a change, sweeping leftover failed-test artifacts, or the
  user says "run tests", "test", or "clean tmp".
---

# Run Tests (shushu)

Wrapper around `uv run pytest` that bakes in shushu's tmp-artifact
hygiene: pytest's `--basetemp` is pinned to `/tmp/shushu-tests/` (in
`pyproject.toml`), passing tests delete their `tmp_path` immediately,
and failed-test trees are retained at most 3-deep for post-mortem.

This script adds:

- A `--clean` flag to wipe `/tmp/shushu-tests/` after the run regardless
  of outcome.
- A `--clean-only` mode for one-shot cleanup without running anything.
- Standard `--parallel` / `--coverage` / `--ci` / `--quick` modes.

## Usage

```bash
# Default: parallel + verbose
bash .claude/skills/run-tests/scripts/test.sh -p

# Quick: parallel + quiet
bash .claude/skills/run-tests/scripts/test.sh -p -q

# Full CI: parallel + coverage + xml report
bash .claude/skills/run-tests/scripts/test.sh --ci

# Specific file
bash .claude/skills/run-tests/scripts/test.sh -p tests/unit/test_cli_set.py

# After a long debugging session — wipe leftover failed-test artifacts
bash .claude/skills/run-tests/scripts/test.sh --clean-only

# Run + always clean afterwards
bash .claude/skills/run-tests/scripts/test.sh -p --clean
```

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--parallel`   | `-p` | `-n auto` via pytest-xdist (uses all cores) |
| `--coverage`   | `-c` | `--cov=shushu --cov-report=term` |
| `--ci`         |      | parallel + coverage + xml + verbose (mirrors `.github/workflows/tests.yml`) |
| `--quick`      | `-q` | quiet output, no coverage |
| `--clean`      | `-k` | `rm -rf /tmp/shushu-tests/` after the run, regardless of pass/fail |
| `--clean-only` |      | wipe `/tmp/shushu-tests/` and exit (no test run) |

Extra positional arguments pass through to pytest verbatim
(`-x` to stop on first failure, `-k "pattern"` to filter, etc.).

## When to use which mode

| Situation | Command |
|-----------|---------|
| After a code change | `bash .claude/skills/run-tests/scripts/test.sh -p` |
| Quick sanity check | `bash .claude/skills/run-tests/scripts/test.sh -p -q` |
| Before a PR or CI sim | `bash .claude/skills/run-tests/scripts/test.sh --ci` |
| Single failing file | `bash .claude/skills/run-tests/scripts/test.sh tests/unit/test_cli_set.py -x` |
| Tmp-artifact pile-up | `bash .claude/skills/run-tests/scripts/test.sh --clean-only` |

## Why a wrapper exists

Three things made an inline `uv run pytest` invocation insufficient:

1. **CI parity.** The `--ci` flag matches `.github/workflows/tests.yml`'s
   pytest line so you can repro CI locally without copy-pasting.
2. **Tmp hygiene.** The pytest config retains failed-test artifacts (3
   most recent) for debugging. After many iterations these accumulate;
   `--clean` and `--clean-only` give a one-line wipe.
3. **Safe default cleanup.** Because `--basetemp` is pinned to
   `/tmp/shushu-tests/`, blasting that root is always safe — there is
   no risk of stomping on unrelated `/tmp/pytest-of-*` dirs from other
   projects.

See `docs/testing.md` for the broader test-isolation conventions
(SHUSHU_HOME env override, smoke-command namespace, integration gate).
