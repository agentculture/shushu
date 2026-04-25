# CLAUDE.md

This file orients Claude Code (claude.ai/code) when working in this
repository.

## Project status

`shushu` is the **agent-first per-OS-user secrets manager CLI** for
the AgentCulture ecosystem. v1 surface is complete: 12 verbs (set,
generate, show, get, env, run, list, delete, overview, doctor,
learn, explain) with admin-mode (`--user` / `--all-users`) for the
seven verbs that admit it. Sibling to
[`zehut`](https://github.com/agentculture/zehut) (identity layer);
patterned on [`afi-cli`](https://github.com/agentculture/afi-cli).

Remote: `https://github.com/agentculture/shushu`.

## Layout

```text
src/shushu/
  __init__.py            # __version__ via importlib.metadata
  __main__.py            # enables `python -m shushu`
  fs.py                  # paths, fcntl locking, atomic write
  alerts.py              # alert_at classification (ok/alerting/expired)
  generate.py            # random_secret(hex|base64)
  users.py               # UserInfo, resolve(name), all_users()
  privilege.py           # require_root, sudo_invoker, run_as_user (setuid-fork)
  store.py               # JSON CRUD; SecretRecord; immutability rules
  admin.py               # as_user / for_each_user / store_paths_for
  cli/
    __init__.py          # argparse parser; main() with error translation
    _errors.py           # ShushuError + EXIT_* constants
    _output.py           # emit_result / emit_error (text + json)
    _translate.py        # exception → ShushuError translation (used by main + admin)
    _commands/
      _write_helper.py   # shared create-or-overwrite (set + generate)
      <verb>.py          # one per verb
tests/
  conftest.py            # autouse _tmp_home + cli_run fixture
  test_cli.py            # --version
  test_self_verify.py    # 13-step end-to-end lifecycle (acceptance gate)
  unit/                  # per-module + per-verb unit tests
  integration/           # gated SHUSHU_DOCKER=1; useradd + setuid-fork
.github/workflows/
  tests.yml              # lint / unit / integration / version-check
  Dockerfile.integration # disposable USER root image for integration tests
docs/
  threat-model.md        # full threat model (expands spec §8)
  rubric-mapping.md      # per-verb purpose / exit codes / JSON shape
  testing.md             # test pyramid + smoke convention
  superpowers/           # design spec + implementation plan (one-time)
.claude/skills/
  pr-review/             # vendored: pr-status.sh adds CI + sonar overview
  run-tests/             # vendored: --clean / --clean-smoke / --smoke-home
  version-bump/          # vendored: bump.py for pyproject + CHANGELOG
```

The console script `shushu` is registered in `pyproject.toml` and
resolves to `shushu.cli:main`.

## Common commands

```bash
# unit + self-verify (skips integration without SHUSHU_DOCKER)
bash .claude/skills/run-tests/scripts/test.sh -p

# CI parity: parallel + coverage + xml + verbose
bash .claude/skills/run-tests/scripts/test.sh --ci

# integration only, inside Docker (needs root for useradd)
docker build -f .github/workflows/Dockerfile.integration -t shushu-int .
docker run --rm -e SHUSHU_DOCKER=1 shushu-int uv run pytest tests/integration -v

# smoke: per-namespace tmp + cleanup, no manual rm
SMOKE=$(bash .claude/skills/run-tests/scripts/test.sh --smoke-home foo)
bash .claude/skills/run-tests/scripts/test.sh --clean-smoke foo
SHUSHU_HOME="$SMOKE" uv run shushu set FOO bar --purpose t
bash .claude/skills/run-tests/scripts/test.sh --clean-smoke foo

# PR status (combines gh pr checks + sonar API + thread tally)
bash .claude/skills/pr-review/scripts/pr-status.sh <PR>
```

## Lint / format

Dev extras: `black`, `isort`, `flake8`, `flake8-bandit`,
`flake8-bugbear`, `pylint`, `bandit`. Line length 100, target py312.

```bash
uv run black src/shushu tests
uv run isort src/shushu tests
uv run flake8 src/shushu tests
uv run bandit -r src/shushu -c pyproject.toml
uv run pylint --errors-only src/shushu
scripts/lint-md.sh
```

`.flake8` carries the only per-file ignores (`tests/*:S101`). Don't
broaden it — real dead imports get deleted, not suppressed.

## Version discipline

Version lives in **one place**: `pyproject.toml`'s `[project].version`.
`src/shushu/__init__.py` resolves `__version__` dynamically via
`importlib.metadata.version("shushu")`. No literal in `__init__.py`
to keep in sync.

The `version-bump` skill at
`.claude/skills/version-bump/scripts/bump.py` automates the bump +
CHANGELOG entry. Every PR must bump (`major` / `minor` / `patch`) —
the `version-check` CI job blocks merge otherwise.

## Python version

`requires-python = ">=3.12"`. PEP 604 union syntax and frozen
dataclasses are used throughout. Don't lower the floor.

## Hidden-secret contract (H2) — non-negotiable

`hidden: true` records:

- Are immutable post-create (no toggling).
- Are refused by `get`, `env`, `show` (exit 64).
- Are omitted from `generate --hidden --json` output (no `value` key).
- Are consumable ONLY via `shushu run --inject VAR=NAME -- cmd`.
- Admin paths inherit ALL of the above — admin can never extract a
  value via the CLI, even for root.

`get`, `env`, `run` deliberately have NO admin flags. `run` is the
only consumer for hidden secrets; it execs the child without ever
passing the value on the command line.

If you're tempted to add a "show value" path for admin, stop —
that's the contract. Use `sudo cat ~user/.local/share/shushu/secrets.json`
if you truly need plaintext (at which point you're outside shushu's
surface).

## Trust boundary

shushu is **single-admin trusted-host**. Multi-tenant hosts, network
services, and remote attackers are out of scope. The threat model at
[`docs/threat-model.md`](docs/threat-model.md) is the source of truth
for what shushu does and does not protect against.

## PR workflow

Every PR follows the same loop:

1. Branch off `main` (e.g. `feat/<short>` or `fix/<short>`).
2. Implement + test locally.
3. Bump version (skill above).
4. Open PR.
5. After CI completes, run
   `bash .claude/skills/pr-review/scripts/pr-status.sh <PR>`. The
   script surfaces failed CI checks, SonarCloud quality-gate status
   with rule keys, per-bot review-pipeline state, and inline-thread
   tally — much faster than chasing each piece individually.
6. Triage (FIX / PUSHBACK), commit fixes, reply + resolve threads
   via `pr-review` skill scripts.
7. Squash-merge.

Recurring PUSHBACKs (already user-approved on prior PRs):

- qodo `__version__` rule violation — `importlib.metadata` is
  strictly stronger than two synced literals. Reply with that
  rationale and resolve.
- SonarCloud `docker:S6471` (USER root in
  `.github/workflows/Dockerfile.integration`) — disposable per-CI-run
  image, sole purpose is integration tests needing real
  `useradd`/`userdel`. Mark REVIEWED/SAFE in SonarCloud UI after
  merge.
