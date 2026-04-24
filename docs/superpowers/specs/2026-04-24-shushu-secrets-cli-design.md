# shushu CLI — v1 design

**Date:** 2026-04-24
**Status:** Approved (pre-implementation)
**Applies to:** `shushu` package on PyPI / TestPyPI
**Repo:** <https://github.com/agentculture/shushu>

## 1. Overview

`shushu` is an **agent-first per-OS-user secrets manager** CLI. It is a
sibling to [`zehut`](https://github.com/agentculture/zehut) in the
AgentCulture ecosystem, patterned on
[`afi-cli`](https://github.com/agentculture/afi-cli) conventions
(noun-verb argparse, agent-first globals, structured errors with exit
codes and remediation, mandatory per-PR version bump, Trusted-Publisher
CI).

shushu is **not** coupled to zehut at runtime — it does not read
`/var/lib/zehut/users.json` and does not require zehut to be installed.
The two CLIs sit side-by-side as culture-ecosystem citizens and share a
design philosophy rather than a state file.

### Mental model

> Every OS user has a private secrets store under their home directory.
> shushu is the CLI that manages it. Admins can provision secrets into
> any user's store but can never extract values through the CLI.

### Scope

**In scope for v1:**

- Per-user secret store at `~/.local/share/shushu/secrets.json`, mode
  `0600`, owned by the invoking OS user.
- Flat key→value namespace per user (no profiles, no sub-users).
- Rich per-secret metadata: `source`, `purpose`, `rotation_howto`,
  `alert_at`, `hidden`, `handed_over_by`, timestamps.
- Random secret generation (`hex` / `base64`, configurable byte length).
- **H2 hiding:** hidden secrets are never readable via `get`/`env`; only
  consumable via `shushu run --inject`.
- Three consumption verbs: `shushu get`, `shushu env`,
  `shushu run --inject`.
- Admin (sudo) mode: `set`, `generate`, `show`, `delete`, `list`,
  `overview`, `doctor` with `--user <name>` / `--all-users`, using
  setuid-fork to write as the target user. **No admin `get` / `env` /
  `run`.**
- afi-style globals: `doctor`, `learn`, `overview`, `explain`. **No
  explicit `init`** — first mutating verb creates the store lazily.
- Linux-only. Python ≥ 3.12. Zero runtime dependencies (stdlib only).

**Explicitly out of scope for v1:**

- **Encryption at rest.** Tracked as a filed issue at project start.
  File on disk is plaintext `0600`. Threat model documents this.
- **Sub-user secrets** (zehut 0.2.0's `subuser` backing is not indexed).
- **Profiles / scopes within one user** — v2 candidate.
- **Versioning / rotation history** — previous value is discarded on
  overwrite.
- **Secret expiry enforcement** — `alert_at` only warns, never deletes.
- **Admin reads values through CLI** — `sudo cat` is the unambiguous
  tool for that.
- **macOS / Windows** — macOS likely works but is untested and
  unsupported; Windows is v3+.
- **MCP / HTTP surfaces** — afi-cli will scaffold later.
- **Integration with the zehut registry.**

## 2. CLI surface

Noun-verb, afi-style. The noun `secret` is the default and dropped from
the command name for ergonomics.

### 2.1 Globals

| Command | Purpose | Sudo? |
|---|---|---|
| `shushu doctor [--all-users\|--user <name>] [--json]` | Store / permission / schema integrity. Setup health. | sudo iff `--all-users`/`--user` |
| `shushu overview [--expired] [--all-users\|--user <name>] [--json]` | Rich metadata snapshot. Secrets' state. `--expired` filters to past-`alert_at`. **No values.** | sudo iff `--all-users`/`--user` |
| `shushu learn [--json]` | Agent-authored self-teaching output (afi pattern). | no |
| `shushu explain <topic>` | Human-readable explanation of any command / concept. | no |
| `shushu --version` | Print `__version__`. | no |

No `shushu init` — first mutating verb creates the store.

### 2.2 Secret verbs

| Verb | Purpose | Sudo? |
|---|---|---|
| `shushu set <name> [<value>] [--source ...] [--purpose ...] [--rotate-howto ...] [--alert-at YYYY-MM-DD] [--hidden]` | Create or update. **With** `<value>` (literal or `-` for stdin): writes value + metadata flags. **Without** `<value>`: updates mutable metadata only. Override-silently on name collision. | self / sudo iff `--user` |
| `shushu show <name> [--json]` | Full record **minus `value`**. Default "inspect a secret" surface. | self / sudo iff `--user` |
| `shushu get <name> [--json]` | Print value. Refused with `EXIT_USER_ERROR` if `hidden: true`. **No `--user`.** | no |
| `shushu env <name1> [<name2> ...]` | Emit `export NAME='value' ...` for `eval $(shushu env FOO BAR)`. Refused if any named secret is hidden. **No `--user`.** | no |
| `shushu run --inject VAR=<name> [--inject ...] -- <cmd> [args...]` | Fork → set env → `os.execvp`. Works for hidden and non-hidden. **No `--user`.** | no |
| `shushu generate <name> [--bytes N] [--encoding hex\|base64] [--source ...] [--purpose ...] [--rotate-howto ...] [--alert-at YYYY-MM-DD] [--hidden]` | Create a random secret. Defaults: `--bytes 32 --encoding hex`. Without `--hidden`, prints value once at creation; with `--hidden`, never prints. | self / sudo iff `--user` |
| `shushu list [--json]` | **Names only, one per line**, scriptable (`shushu list \| xargs …`). No alert decoration — `overview` owns that. | self / sudo iff `--user` / `--all-users` |
| `shushu delete <name>` | Remove from store. | self / sudo iff `--user` |

`list` vs. `overview` distinction: `list` is pipe-friendly (names only);
`overview` is audit-friendly (rich metadata, alert classification,
`--expired` filter).

### 2.3 Field mutability

- **Mutable via `shushu set <name> [--flags]` (no value positional):**
  `purpose`, `rotation_howto`, `alert_at`.
- **Value mutable** via `shushu set <name> <value>` (overwrites previous
  value).
- **Fully immutable post-create:** `name`, `source`, `hidden`,
  `created_at`, `handed_over_by`. Passing those as flags on an existing
  secret → `EXIT_USER_ERROR`. To change: `delete` + re-create.

### 2.4 Admin `--user` / `--all-users`

- `--user <name>` valid on: `set`, `show`, `generate`, `list`, `delete`,
  `overview`, `doctor`.
- `--all-users` (read-only) valid on: `list`, `overview`, `doctor`.
- Rejected on: `get`, `env`, `run` — no value-extraction path for admin.
- Requires `os.geteuid() == 0`, else `EXIT_PRIVILEGE` with
  `re-run with: sudo $(which shushu) …`.
- `--user` and `--all-users` are mutually exclusive.
- `--all-users` is read-only; write verbs (`set`, `generate`, `delete`)
  require a specific `--user`.

### 2.5 Output discipline

- `--json` on any verb → machine-parseable JSON only on stdout.
- Warnings (overwrite notice, alert banners) → stderr, so agent stdout
  stays clean.
- Hidden-secret refusals are structured `EXIT_USER_ERROR` responses with
  a `remediation` field.

## 3. Architecture

### 3.1 Package layout

```text
shushu/
├── .claude/skills/version-bump/         # vendored from afi-cli
├── .github/workflows/
│   ├── tests.yml
│   ├── publish.yml
│   └── security-checks.yml
├── .markdownlint-cli2.yaml
├── CHANGELOG.md
├── CLAUDE.md
├── LICENSE
├── README.md
├── docs/
│   ├── threat-model.md
│   ├── testing.md
│   ├── rubric-mapping.md
│   └── superpowers/specs/2026-04-24-shushu-secrets-cli-design.md
├── pyproject.toml
├── scripts/lint-md.sh
├── tests/
│   ├── unit/
│   │   ├── test_store.py
│   │   ├── test_cli_set.py
│   │   ├── test_cli_get_env_run.py
│   │   ├── test_cli_generate.py
│   │   ├── test_cli_show_list_overview.py
│   │   ├── test_cli_delete.py
│   │   ├── test_admin_refusal.py
│   │   ├── test_mutability.py
│   │   ├── test_hidden_refusal.py
│   │   └── test_errors.py
│   ├── integration/
│   │   ├── test_admin_handoff.py
│   │   └── test_all_users_enumeration.py
│   ├── test_cli.py
│   └── test_self_verify.py
├── uv.lock
└── src/shushu/
    ├── __init__.py                      # __version__ via importlib.metadata
    ├── __main__.py
    ├── cli/
    │   ├── __init__.py                  # main, _build_parser, _dispatch, error routing
    │   ├── _commands/
    │   │   ├── doctor.py
    │   │   ├── explain.py
    │   │   ├── learn.py
    │   │   ├── overview.py
    │   │   ├── set.py
    │   │   ├── show.py
    │   │   ├── get.py
    │   │   ├── env.py
    │   │   ├── run.py
    │   │   ├── generate.py
    │   │   ├── list.py
    │   │   └── delete.py
    │   ├── _errors.py                   # ShushuError + EXIT_* constants
    │   └── _output.py                   # emit_result / emit_diagnostic / emit_error
    ├── store.py
    ├── fs.py
    ├── privilege.py
    ├── users.py
    ├── generate.py
    └── alerts.py
```

### 3.2 Module responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `shushu.cli` | argparse plumbing, dispatch, error routing. Pure UI — no state mutation. | `_errors`, `_output`, command modules |
| `shushu.store` | Load/save/mutate a user's `secrets.json`. Enforces schema_version, immutability rules, alert-date parsing. Only module that writes secrets to disk. | `fs`, `alerts` |
| `shushu.fs` | Path constants (respects `SHUSHU_HOME` for tests), `fcntl` advisory locking, atomic write-temp → fsync → rename. | stdlib only |
| `shushu.privilege` | `geteuid()` checks, sudo-advice message assembly, setuid-fork helper for admin handoff. | stdlib only |
| `shushu.users` | `pwd.getpwall()` enumeration for `--all-users`; resolve `<name>` → `(uid, gid, home)`. | stdlib only |
| `shushu.generate` | `secrets.token_bytes(n)` + hex/base64 encoding. | stdlib only |
| `shushu.alerts` | Parse `alert_at`, classify a record as `ok` / `alerting` (within 30 days) / `expired`. | stdlib only |

**Dependency direction:**
`cli → (_commands/*) → store / generate / alerts / users / privilege → fs`.
`privilege` is leaf-level. No module imports `cli`. No circular imports.

**Error routing.** Every handler raises `ShushuError(code, message,
remediation)`. `cli._dispatch` catches, routes through
`_output.emit_error`, returns the exit code. Unknown exceptions wrap to
`EXIT_INTERNAL` with a bug-report hint. No Python tracebacks reach end
users.

### 3.3 Path constants

```python
# shushu.fs — defaults (SHUSHU_HOME overrides for tests only)
USER_STORE_DIR  = Path(os.environ.get("SHUSHU_HOME") or Path.home() / ".local/share/shushu")
USER_STORE_FILE = USER_STORE_DIR / "secrets.json"
USER_LOCK_FILE  = USER_STORE_DIR / ".lock"
```

Directory mode `0700`, file mode `0600`, both owned by the invoking
user. In admin handoff, the setuid-fork helper guarantees the same modes
and ownership for the target user — the on-disk file is
indistinguishable from one the target user wrote herself, except for
the `handed_over_by` metadata field.

## 4. Storage schema

### 4.1 On-disk layout

```text
~/.local/share/shushu/                    # 0700 owner:owner
├── secrets.json                          # 0600 owner:owner
└── .lock                                 # 0600 owner:owner  (fcntl advisory lock)
```

- Directory created by the first mutating verb. Mode set explicitly
  (umask ignored).
- File written atomically: write-temp-in-same-dir → `os.fsync` →
  `os.replace`.
- Writers take `fcntl.LOCK_EX` on `.lock`; readers take `LOCK_SH`.
  Same discipline as zehut.
- `SHUSHU_HOME` overrides the base path for tests only; not advertised
  to end users.

### 4.2 `secrets.json` shape

```json
{
  "schema_version": 1,
  "secrets": [
    {
      "name": "OPENAI_API_KEY",
      "value": "sk-...",
      "hidden": false,
      "source": "https://platform.openai.com",
      "purpose": "Project X agent pipeline",
      "rotation_howto": "Log in → Settings → API Keys → Rotate",
      "alert_at": "2026-10-01",
      "handed_over_by": null,
      "created_at": "2026-04-24T12:00:00Z",
      "updated_at": "2026-04-24T12:00:00Z"
    },
    {
      "name": "INTERNAL_SIGNING_KEY",
      "value": "a3f2...",
      "hidden": true,
      "source": "admin:ori",
      "purpose": "Webhook signing for agent-bot",
      "rotation_howto": "shushu generate INTERNAL_SIGNING_KEY --bytes 32 --hidden",
      "alert_at": "2027-04-24",
      "handed_over_by": "ori",
      "created_at": "2026-04-24T12:05:00Z",
      "updated_at": "2026-04-24T12:05:00Z"
    }
  ]
}
```

### 4.3 Field reference

| Field | Type | Required | Mutable? | Notes |
|---|---|---|---|---|
| `name` | string | yes | no | Primary key. Regex `^[A-Z_][A-Z0-9_]{0,63}$` — env-var-safe. |
| `value` | string | yes | yes (via `set <name> <value>`) | Arbitrary UTF-8. Binary secrets encode to hex/base64 by the caller. |
| `hidden` | bool | yes | **no** | Set at create; never toggled. |
| `source` | string | yes | **no** | Default `"localhost"` on both `set` and `generate` when `--source` is omitted. `"admin:<sudo_user>"` on admin handoff. Otherwise the URL or free text passed via `--source`. |
| `purpose` | string | optional (default `""`) | yes | Free text. Why this secret exists. Empty is allowed; `doctor` warns. |
| `rotation_howto` | string | optional (default `""`) | yes | Free text. Procedure for rotation. Empty is allowed; `doctor` warns. |
| `alert_at` | ISO-8601 **date** or `null` | optional | yes | Date only (no time). Parsed via `datetime.date.fromisoformat`. Past dates are valid — they classify as `expired` in `overview`. |
| `handed_over_by` | string or `null` | yes | **no** | `null` for self-written; `os.environ["SUDO_USER"]` (fallback: `pwd.getpwuid(os.getuid()).pw_name`) for handoff. |
| `created_at` | ISO-8601 **datetime**, UTC, seconds precision | yes | **no** | E.g. `2026-04-24T12:00:00Z`. |
| `updated_at` | ISO-8601 **datetime**, UTC, seconds precision | yes | yes (auto) | Refreshed on every mutation. |

**Datetime discipline.** `alert_at` is date-only because alerting is
coarse. `created_at` and `updated_at` are full UTC datetimes (seconds
precision) because knowing *when* a credential was rolled or issued
matters for audit.

### 4.4 Validation rules

- `name` format: `^[A-Z_][A-Z0-9_]{0,63}$`. Matches POSIX env-var
  conventions so `shushu env` / `run --inject` can inject without
  escaping tricks.
- `alert_at`: valid ISO date or absent / `null`.
- `hidden` and `handed_over_by`: rejected as `--flag` inputs on any
  verb that isn't `generate`/`set` at create time, or any non-admin
  verb respectively.
- `source` with the shape `admin:<name>` is accepted only when written
  by the admin handoff path. The CLI refuses `--source admin:...` from
  an unprivileged caller (prevents forged provenance).

### 4.5 Concurrency & consistency

- Every mutation: full read → mutate → atomic-write cycle under
  `LOCK_EX`. No partial updates.
- Schema version checked on every read. Mismatch → `EXIT_STATE` with
  `your shushu store uses schema_version=N, this binary supports
  schema_version=1; upgrade shushu or file a migration issue`. No
  `shushu migrate` in v1.
- `.lock` is a persistent sentinel (never removed).

### 4.6 Admin handoff mechanics

Given `sudo shushu set --user alice FOO <value>`:

1. Parent validates `os.geteuid() == 0` and resolves alice via
   `pwd.getpwnam("alice")` → `(uid, gid, home)`. No home dir →
   `EXIT_USER_ERROR`.
2. Parent captures `os.environ.get("SUDO_USER")` (fallback
   `pwd.getpwuid(os.getuid()).pw_name`).
3. Parent `fork()`s. In the child:
   - `os.setgroups([])`
   - `os.setgid(gid)` + `os.setegid(gid)`
   - `os.setuid(uid)` + `os.seteuid(uid)` (setuid after setgid per POSIX)
   - Create `~alice/.local/share/shushu/` (`0700`) if absent;
     load/lock/mutate/write-atomic `secrets.json`; release lock; exit.
4. Parent `waitpid`s and surfaces the child's exit code.

Resulting file: owned by `alice:alice`, mode `0600`, identical to
self-written — except `source = "admin:ori"` and
`handed_over_by = "ori"`. No root-owned files left in user homes.

## 5. Error model

### 5.1 Exit codes

| Code | Name | Meaning |
|---|---|---|
| 0 | `EXIT_SUCCESS` | — |
| 64 | `EXIT_USER_ERROR` | Bad args, unknown `<name>`, attempt to mutate immutable field, invalid date, name fails regex, `get`/`env` on hidden secret, `--source admin:*` without sudo. |
| 65 | `EXIT_STATE` | Store missing / corrupt / schema_version mismatch / lockfile unreachable. |
| 66 | `EXIT_PRIVILEGE` | `--user` / `--all-users` without `euid==0`. |
| 67 | `EXIT_BACKEND` | setuid-fork child crashed; `pwd.getpwnam` failed; home dir absent. |
| 68 | `EXIT_CONFLICT` | Reserved for parity with zehut + future profiles/versioning. |
| 70 | `EXIT_INTERNAL` | Wrapped unexpected exception. Ships `please file an issue at github.com/agentculture/shushu/issues with: <short error>`. |

### 5.2 Notable error surfaces

| Scenario | Code | Remediation |
|---|---|---|
| `shushu get FOO` when `hidden: true` | `EXIT_USER_ERROR` | `FOO is a hidden secret; use: shushu run --inject VAR=FOO -- <cmd>` |
| `shushu env FOO BAR` where `BAR` is hidden | `EXIT_USER_ERROR` | `BAR is hidden; exclude it or use: shushu run --inject BAR=BAR -- <cmd>` |
| `shushu set --user alice FOO <v>` without sudo | `EXIT_PRIVILEGE` | `re-run with: sudo $(which shushu) set --user alice FOO <v>` |
| `shushu set FOO --source "..."` on existing secret | `EXIT_USER_ERROR` | `source is immutable post-create; delete and re-create to change` |
| `shushu set FOO --alert-at 2026-13-40` | `EXIT_USER_ERROR` | `invalid ISO date; use YYYY-MM-DD` |
| `shushu set FOO --source admin:xyz` as non-root | `EXIT_USER_ERROR` | `source 'admin:*' is reserved for sudo handoff; drop the flag` |
| `shushu get BAR` where BAR absent | `EXIT_USER_ERROR` | `no secret named BAR; see: shushu list` |
| `shushu doctor --all-users` as non-root | `EXIT_PRIVILEGE` | `re-run with: sudo $(which shushu) doctor --all-users` |
| `sudo shushu set --user ghost FOO v` (ghost not in passwd) | `EXIT_BACKEND` | `no OS user 'ghost' on this host; see: getent passwd` |
| Store `schema_version != 1` | `EXIT_STATE` | `your shushu store uses schema_version=N, this binary supports schema_version=1; upgrade shushu or file a migration issue` |
| `shushu run --inject` malformed arg | `EXIT_USER_ERROR` | Concrete: e.g. `--inject "=FOO" has empty variable name; expected form is VAR=NAME` |

Malformed `--inject` errors must name the specific malformation
(empty name, empty var, missing `=`, duplicate var) and show the
expected form. Users should not have to read `--help` to understand
what went wrong.

### 5.3 `doctor` checks

Each returns `PASS` / `WARN` / `FAIL` with remediation. Read-only in v1.

For the invoking user:

1. `~/.local/share/shushu/` exists, is a directory, mode `0700`, owner = invoker.
2. `secrets.json` exists, is a file, mode `0600`, owner = invoker, parses as JSON, `schema_version == 1`.
3. `.lock` exists, mode `0600`, owner = invoker.
4. Every record satisfies the v1 field constraints (name regex, valid
   `alert_at`, `hidden` is bool, etc.).
5. For every record with non-null `alert_at`: classify as `ok` /
   `alerting` (within 30 days) / `expired`. Report counts; `expired` →
   `WARN`.
6. For every record with empty `rotation_howto`: `WARN` with
   `consider: shushu set <name> --rotate-howto "..."`.
   For every record with empty `purpose`: `WARN` with
   `consider: shushu set <name> --purpose "..."`.

Additional with `--user <name>` / `--all-users` (sudo-gated):

7. `pwd.getpwnam(name)` resolves and home directory exists.
8. Run checks 1–6 against that user's store. For `--all-users`, iterate
   `pwd.getpwall()`, skip users whose home doesn't exist or who have no
   shushu store (not an error).
9. **Orphan store check:** any `*/shushu/` directory whose owning uid is
   no longer in passwd → `WARN`.

`doctor` never reads `value` fields.

### 5.4 Output shape

Text (default):

```text
shushu: error: FOO is a hidden secret; use `shushu run --inject VAR=FOO -- <cmd>`
```

JSON (`--json`):

```json
{
  "ok": false,
  "error": {
    "code": 64,
    "name": "EXIT_USER_ERROR",
    "message": "FOO is a hidden secret",
    "remediation": "use `shushu run --inject VAR=FOO -- <cmd>`"
  }
}
```

Every success response in `--json` mode has `ok: true` + verb-specific
payload. Full payload schemas live in `docs/rubric-mapping.md`.

## 6. Packaging, versioning, CI

### 6.1 Packaging

- Build backend: **hatchling**.
- `pyproject.toml`: `requires-python = ">=3.12"` (bumped from scaffold's
  3.10 for parity with zehut).
- **Zero runtime dependencies** — stdlib only: `argparse`, `json`,
  `fcntl`, `pwd`, `pathlib`, `secrets`, `base64`, `datetime`, `os`,
  `sys`. `os.execvp` for `run --inject` (no `subprocess`).
- `project.scripts`: `shushu = "shushu.cli:main"` (preserved from
  scaffold).
- src-layout: `src/shushu/…` (preserved).
- Install: `uv tool install shushu`. Admin: `sudo $(which shushu) …` —
  `privilege.py` assembles this hint to work around `uv tool install`'s
  `~/.local/bin` placement relative to root's `secure_path`.
- First published version: `0.1.0` (pre-alpha classifier). PyPI +
  TestPyPI.

### 6.2 Dev dependency group

```
pytest, pytest-xdist, pytest-cov, coverage,
black, isort, flake8, flake8-bandit, flake8-bugbear, pylint, bandit,
pre-commit
```

Preserve scaffold's `[tool.black]`, `[tool.isort]`,
`[tool.pytest.ini_options]`; adjust `target-version` to `py312`.

### 6.3 Versioning

- `src/shushu/__init__.py`: `__version__ = importlib.metadata.version("shushu")`.
  Replaces the scaffold's literal. Single source of truth moves to
  `pyproject.toml`.
- **Every PR MUST bump.** Enforced by the `version-check` job in
  `tests.yml`.
- `.claude/skills/version-bump/` vendored from afi-cli. Usage:
  `python3 .claude/skills/version-bump/scripts/bump.py {patch|minor|major}`
  with a JSON changelog object on stdin.
- Bump semantics:
  - **patch** — docs / config / CI / internal refactor.
  - **minor** — new verb, new flag, new metadata field, new exit code.
  - **major** — `schema_version` bump, removed verb/flag/field,
    exit-code reshuffle, default behavior change.
- `CHANGELOG.md` entries 1:1 with merged PRs.

### 6.4 CI workflows

| Workflow | Trigger | Jobs |
|---|---|---|
| `tests.yml` | PR, push to main | `lint` (flake8/pylint/bandit/black --check/isort --check), `test` (pytest, Python 3.12, Docker for integration), `version-check`, `markdown-lint` |
| `publish.yml` | PR → TestPyPI; push to main → PyPI | Trusted Publishing (OIDC), `uv build`, upload |
| `security-checks.yml` | weekly + manual | bandit, pip-audit, trivy fs scan |

**Integration tests in Docker.** The setuid-fork path requires real uid
changes. CI spins up a container, creates `alice` and `bob`, runs
shushu as root with `--user`, re-invokes as each to verify the written
store is self-consistent. Gated locally with
`@pytest.mark.skipif(os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"))`.

### 6.5 Markdown linting

- `.markdownlint-cli2.yaml` at repo root, mirroring zehut (MD013/MD060
  disabled).
- `scripts/lint-md.sh` wraps `markdownlint-cli2 --fix`.
- Pre-commit runs it in check-only mode.

### 6.6 Repo transition from current scaffold

- **Keep:** `pyproject.toml` skeleton, `[project.scripts]` wiring,
  src-layout, existing `tests/` directory, license, `.gitignore`.
- **Replace:** `src/shushu/cli.py` → `src/shushu/cli/` package;
  `src/shushu/__init__.py` → `importlib.metadata.version`.
- **Add:** all modules in §3.1; `docs/` tree; `.github/workflows/`;
  `.claude/skills/version-bump/`; `.markdownlint-cli2.yaml`;
  `scripts/lint-md.sh`; `CHANGELOG.md`; updated `CLAUDE.md`.
- **Rewrite:** `README.md` to describe the actual v1 CLI surface.

## 7. Testing strategy

### 7.1 Unit tests (`tests/unit/`)

- No real sudo, no real `setuid`, no real `/home/*` paths — all via
  `SHUSHU_HOME` → per-test `tmp_path`.
- No network. No subprocess spawning except `run --inject`'s
  `os.execvp`, exercised by a `sys.executable -c` round-trip.
- Coverage targets: `store` ≥ 95%, `cli/_commands/*` ≥ 90%, `alerts`
  100%, `privilege` ≥ 80%.
- Key cases: store integrity, overwrite semantics, immutability
  enforcement, hidden refusal on `get`/`env`, `env` shell-safe
  escaping, `run --inject` env round-trip, admin refusal without sudo,
  generate randomness/encoding, error-shape schema.

### 7.2 Integration tests (`tests/integration/`)

Gated with
`@pytest.mark.skipif(os.geteuid() != 0 and not os.getenv("SHUSHU_DOCKER"))`.

- `test_admin_handoff.py`: root creates `alice`/`bob`, admin `set`
  then `generate --hidden` into each, drop to each user, verify
  metadata + values as expected, verify file ownership and modes.
- `test_all_users_enumeration.py`: `sudo shushu overview --all-users
  --json` includes both users' metadata, zero `value` fields anywhere.
- **File-ownership invariant:** no root-owned files under any user
  home after the suite.

### 7.3 Self-verify (`tests/test_self_verify.py`)

Single process, `SHUSHU_HOME=<tmp>`, no sudo. 13-step lifecycle:

1. `shushu set FOO bar --purpose "self-test" --alert-at 2099-01-01` → `EXIT_SUCCESS`.
2. `shushu generate BAZ --bytes 16 --hidden` → `EXIT_SUCCESS`, no value printed.
3. `shushu list --json` → 2 records.
4. `shushu show FOO --json` → record present, no `value` key.
5. `shushu get FOO` → prints `bar`.
6. `shushu get BAZ` → `EXIT_USER_ERROR` (hidden refusal).
7. `shushu env FOO` → valid shell export line.
8. `shushu run --inject X=BAZ -- python -c 'import os; print(len(os.environ["X"]))'` → prints `32`.
9. `shushu set FOO --purpose "updated"` → `EXIT_SUCCESS`, value unchanged.
10. `shushu set FOO --hidden` → `EXIT_USER_ERROR` (immutable).
11. `shushu delete FOO` → `EXIT_SUCCESS`.
12. `shushu doctor --json` → all-PASS.
13. `shushu overview --json` → 1 record remaining (`BAZ`).

### 7.4 Coverage floor

`[tool.coverage.report] fail_under = 70`.

### 7.5 What we don't test

- Cryptographic quality of `secrets.token_bytes` (trust stdlib).
- Every ENOSPC / EPERM permutation (trust the OS).
- Exotic filesystem semantics (bind mounts, overlayfs).

## 8. Threat model (stub — full text in `docs/threat-model.md`)

### 8.1 Trust boundary

The host OS filesystem and uid model. `~/.local/share/shushu/secrets.json`
(mode `0600`, owned by the user) is protected by exactly the same
mechanisms that protect `~/.ssh/id_rsa`. shushu adds **no cryptographic
layer on top** in v1.

### 8.2 Adversary model (v1)

Single-admin trusted host. Non-root local users MUST NOT be able to:

1. Read another user's secrets through shushu.
2. Write into another user's store through shushu.
3. Forge provenance (`source = "admin:*"`).
4. Extract another user's plaintext values through any admin verb.
5. Impersonate another user via ambient resolution.

Multi-tenant hosts, network services, remote attackers, and
hardware-level adversaries are out of scope.

### 8.3 Risk surfaces

1. **setuid-fork handoff.** `setgroups([])` + `setgid` + `setuid`, in
   that order; all return values checked; capabilities drop on setuid
   from euid 0 (no `SECBIT_KEEP_CAPS`). TOCTOU between `getpwnam` and
   `setuid` is residual on trusted hosts.
2. **File-mode drift.** Explicit `0600`/`0700` on write; `doctor`
   warns on drift.
3. **Hidden-secret contract.** CLI contract, not cryptographic. File
   is plaintext on disk; user can `cat` their own JSON. Tracked as the
   **encryption-at-rest issue** filed at project start.
4. **Admin metadata exfiltration.** `overview --all-users` reveals
   names/sources/purposes — deliberate, for audit. Naming discipline
   is outside shushu's scope.
5. **Command-line argument leakage.** Docs lead with
   `shushu set FOO -` (stdin); literal-value form is called out as
   "convenient for scripting, visible in process lists."
   `run --inject` takes only names, never values.
6. **Input validation.** Name regex constrains to env-var-safe forms;
   `shushu env` single-quotes values and escapes embedded `'` as
   `'\''` (POSIX-safe), round-trip-fuzz-tested.

### 8.4 Residual risks (documented, not mitigated in v1)

| Risk | Status |
|---|---|
| Plaintext at rest | Issue filed at project start; v2 candidate. |
| Root can `cat` everything | CLI surface doesn't expose it; accepted. |
| Orphan stores after user deletion | `doctor --all-users` warns; v2 cleanup verb. |
| setuid-fork TOCTOU with `usermod` | Accepted on trusted-admin host. |
| Shell-history leakage of literal `set <name> <value>` | Doc + `explain` guide to stdin form. |

## 9. Acceptance for v1

v1 is complete when:

- Every verb in §2 is implemented with documented flags and behaviors.
- Every `--user` / `--all-users` path is `euid == 0`-gated and writes
  go through the setuid-fork helper.
- Every admin-blocked path (`get`/`env`/`run` with `--user`) rejects
  with the documented remediation.
- Every hidden-secret refusal path returns `EXIT_USER_ERROR` with
  remediation pointing at `shushu run --inject`.
- Every immutable-field mutation attempt returns `EXIT_USER_ERROR`.
- `shushu run --inject` never leaks values into `argv` (verified).
- `shushu env` output round-trips through
  `bash -c "$(shushu env ...)"` for pathological values.
- `tests/test_self_verify.py` passes.
- Integration tests pass in Docker CI: real `useradd`'d alice/bob,
  admin handoff verified file-ownership, zero root-owned files in
  either home after the suite.
- Coverage ≥ 70%; `store` ≥ 95%.
- `shushu doctor --json` returns all-PASS on a clean self-managed
  install and on an admin-provisioned bob.
- `tests.yml` passes with `version-check`, lint, pytest matrix,
  markdown-lint.
- `publish.yml` successfully uploads `0.1.0` to TestPyPI on PR.
- `docs/threat-model.md` and `docs/rubric-mapping.md` exist and are
  linked from `README.md`.
- **The encryption-at-rest issue is filed** on
  `agentculture/shushu`, referenced from the threat model, with a v2
  candidates stub (age; libsecret; pass/gpg).
- `shushu learn --json` emits a structured agent-authored skill
  covering all verbs (afi rubric).
- `shushu explain <topic>` answers for every verb and for the
  concepts `hidden`, `admin`, `alert_at`.

## 10. Open questions for implementation

Small enough that the plan resolves them:

1. **Alert classification uses UTC.** `alerts.py` compares today's UTC
   date against `alert_at`. No local-time / DST handling.
   `created_at` / `updated_at` are full UTC datetimes (seconds
   precision); `alert_at` is date-only.
2. **`shushu run --inject` argv discipline.** `action="append"` on
   argparse. Malformed inputs raise `EXIT_USER_ERROR` with a concrete
   message naming the malformation (empty name, empty var, missing
   `=`, duplicate var) and the expected form `VAR=NAME`. Duplicate
   var → last-wins (shell assignment semantics), logged to stderr.
3. **`shushu env` POSIX quoting.** Single-quote the value; replace
   embedded `'` with `'\''`. Reference in `cli/_commands/env.py`.
4. **`list` vs `overview`.** `list` = names only, one per line,
   scriptable. `overview` = rich metadata with alert classification,
   `--expired` filter, `--json`. No decoration on `list`.
5. **`uv tool install` path hint.** Use `shutil.which("shushu")` at
   advice-message assembly to produce
   `re-run with: sudo <resolved_path> …`. Cover `~/.local/bin` and
   custom uv prefixes.
6. **Version test rewrite.** The scaffold's
   `test_default_prints_version` asserts `__version__` literal matches
   `pyproject`. After the `importlib.metadata` switch, rewrite to
   invoke `main(["--version"])` and assert stdout matches
   `importlib.metadata.version("shushu")`.

## 11. Related documents

- `docs/threat-model.md` — full threat model (expands §8).
- `docs/testing.md` — test env hooks (`SHUSHU_HOME`, `SHUSHU_DOCKER`).
- `docs/rubric-mapping.md` — afi-rubric mapping (learn/explain/exit
  codes, JSON payload schemas per verb).
- Sibling design: [zehut v1 design](../../../../zehut/docs/superpowers/specs/2026-04-24-zehut-cli-design.md).
- Patterned on: [afi-cli](https://github.com/agentculture/afi-cli)
  (conventions, rubric, versioning).
