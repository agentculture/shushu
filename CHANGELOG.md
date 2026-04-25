# Changelog

All notable changes to shushu are recorded here. Entries are kept 1:1
with merged PRs per the per-PR version bump discipline documented in
`CLAUDE.md`.

## [Unreleased]

- (nothing yet — v0.6.0 cut; next bump on the following PR)

## [0.6.0] — 2026-04-25

### Added

- `shushu get NAME [--json]` — print a secret's value to stdout. Refuses if `hidden=True` (HiddenError → exit 64 with remediation pointing at `shushu run --inject`). The `get` parser deliberately does NOT register `--user` / `--all-users`: admin can never extract values via the CLI (H2 hidden-secret contract).
- `shushu env NAME1 [NAME2 ...]` — emit POSIX single-quoted `export` lines for `eval $(shushu env A B)`. Refuses **the whole call** if any named secret is hidden (atomicity — never a partial print before the error). Single-quote escaping round-trips through bash for arbitrary values (verified by `test_env_escapes_single_quotes_posix_safe`).
- `shushu run --inject VAR=NAME [--inject ...] -- cmd [args...]` — `os.execvpe` the child process with secrets stamped into env. Both visible and hidden secrets are allowed (this is the only consumer for hidden ones). `--inject` parsing emits explicit per-case malform errors (missing `=`, empty VAR, empty NAME). Last-wins on duplicate VAR. Leading `--` after argparse REMAINDER is stripped. `FileNotFoundError` from execvpe → exit 64 with a "check PATH" hint.
- `shushu list [--json] [--user NAME|--all-users]` — names only, sorted, one per line. `--json` emits `{"ok": true, "names": [...]}`. `--user` / `--all-users` raise structured `not yet implemented` (exit 64) pending Task 26.
- `shushu delete NAME [--json] [--user NAME]` — remove a secret. NotFoundError → exit 64 via main()'s wrapping. `--user` deferred to Task 26.

### Tooling

- `.claude/skills/run-tests/scripts/test.sh` gained `--clean-smoke <name>` and `--smoke-home <name>` flags. Smoke flows now never need a manual `rm -rf` against `/tmp/shushu-tests/*`; the wrapper validates the namespace (rejects `..`, `/`, empty, etc.) before touching disk. Documented in `docs/testing.md` and the SKILL.md.

### Tests

- 19 new unit tests covering the 5 new verbs end-to-end (4 + 4 + 6 + 3 + 2). Total: 114 tests passing.

## [0.5.0] — 2026-04-25

### Added

- `shushu set NAME [value] [--flags]` — first write-surface verb. With value: create or update (writes value + metadata); use `-` for value to read from stdin (preferred for real secrets, strips one trailing newline). Without value: metadata-only update via `store.update_metadata` (`--purpose` / `--rotate-howto` / `--alert-at`). On overwrite, `source` and `hidden` are immutable post-create — attempts to change them exit 64 with a remediation pointing to `delete + re-create`. Refuses `--source admin:*` from non-root callers (reserved for sudo handoff). `--user` raises a structured `not yet implemented` error pending Task 26 (after `privilege.require_root` guard, so non-root invocations get the standard EXIT_PRIVILEGE 66).
- `shushu generate NAME [--bytes N] [--encoding hex|base64] [--flags]` — random secret generation via `shushu.generate.random_secret`. Defaults to 32 bytes hex. `--hidden` makes the value write-only-via-inject: text mode never prints it; JSON mode omits the `value` field. Reuses `store.set_secret` so it inherits the same write path as `set`. Same `admin:*` source rejection and `--user` deferral as `set`.
- `shushu show NAME [--json] [--user NAME]` — metadata-only read. **Never** prints `value`. Text mode prints `key: value` lines per metadata field; `--json` emits the structured dict. Missing record bubbles `store.NotFoundError` to main()'s wrapping → exit 64 with `see: shushu list`.

### Tests

- 15 new unit tests across `set` (9), `generate` (4), `show` (2). Total: 92 tests passing.

## [0.4.0] — 2026-04-25

### Added

- `shushu learn` — agent-authored self-teaching output. Text mode prints a markdown summary of every verb and concept; `--json` returns a structured payload (`verbs`, `descriptions`, `concepts`) for machine consumers.
- `shushu explain <topic>` — short markdown body per topic. Topics include every verb plus the conceptual entries `hidden`, `admin`, `alert_at`. Unknown topics exit 64 with a `try: ...` remediation hint.
- `shushu doctor` — read-only setup / permission / schema integrity checks against the invoker's own store. Verifies store dir mode (`0o700`), secrets file mode (`0o600`), `schema_version`, and per-record validity (empty `purpose` / `rotation_howto`, expired or alerting `alert_at`). Text mode prints `[STATUS] name: detail` per check + a summary line; `--json` returns `{checks: [...], summary: {pass, warn, fail}}`. Exit 0 unless any FAIL (then `EXIT_STATE` = 65). `--user` / `--all-users` raise a `not yet implemented` error pending Task 26.
- `shushu overview` — rich metadata snapshot of every secret in the invoker's store with alert classification (`ok` / `alerting` / `expired`). `--expired` filters to expired records only; `--json` returns the full structured payload. **Never prints `value`.** `--user` / `--all-users` raise a `not yet implemented` error pending Task 26.

### Tests

- 11 new unit tests covering the `learn`, `explain`, `doctor`, and `overview` verbs end-to-end. Total: 77 tests passing.

## [0.3.1] — 2026-04-24

### Fixed

- **CI tests pipeline running again.** The `tests` workflow had been silently failing at workflow-validation time on every run since PR #2, because the `if: hashFiles('tests/integration/**') != ''` gate added on the `integration` job is rejected by GitHub Actions before any job starts (visible as a 0s "workflow file issue"). Removed the `integration` job entirely; it returns in Task 26 once `tests/integration/` exists. lint / unit / version-check now actually run on every PR.
- `store.load()` TOCTOU: dropped the `paths.file.exists()` precheck outside the lock; existence is now decided inside `_load_raw_unlocked()` under `LOCK_SH`. (Copilot, Qodo)
- `_json_to_record()` strict bool check on `hidden`: `bool("false")` is truthy and previously coerced corrupt stores into "hidden" silently. Now raises `StateError`. (Copilot)
- `_load_raw_unlocked()` validates the `secrets` field is a list and catches `TypeError` from malformed records, so non-list / non-dict input surfaces as `StateError` instead of bypassing the schema-enforced contract. (Copilot)
- `fs.ensure_store_dir()` lockfile creation no longer races: dropped `O_EXCL` and the `exists()` precheck so concurrent first-run callers don't crash with `FileExistsError`. (Qodo)
- `cli/_output.py::emit_error` now defaults to `sys.stdout` when `json_mode=True` (and `sys.stderr` otherwise). The `--json` contract — one JSON object on stdout for both success and error responses — was previously broken for errors. (Copilot, Qodo)
- `tests/unit/test_users.py` now compares against `os.geteuid()` to match `users.current()`'s implementation; previously the test would have failed under any `setuid`/sudo scenario where `uid != euid`. (Copilot)
- `tests/unit/test_privilege.py`: renamed two test functions whose names contained uppercase `SUDO_USER` to satisfy `python:S1542` (snake_case convention). (SonarCloud)

### Tests

- Added regression tests for non-list `secrets`, non-bool `hidden`, and `emit_error` default-stream behavior in both modes.

## [0.3.0] — 2026-04-24

### Added

- `shushu.fs` — paths, fcntl advisory locking (shared/exclusive), atomic write-temp-fsync-rename. Respects `SHUSHU_HOME` env override for tests.
- `shushu.alerts` — UTC-based classification of a record's `alert_at` as `ok` / `alerting` (≤30 days) / `expired`.
- `shushu.generate` — random hex/base64 secrets via `secrets.token_bytes` (32-byte default).
- `shushu.users` — `pwd`-backed `UserInfo` dataclass + `current` / `resolve` / `all_users`.
- `shushu.privilege` — `PrivilegeError`, `require_root`, `sudo_invoker`, `resolve_shushu_path`, and `run_as_user` setuid-fork helper for admin handoff.
- `shushu.store` — schema-enforced JSON CRUD: `SecretRecord` / `StoreData` dataclasses, `load` / `set_secret` / `update_metadata` / `get_value` / `get_record` / `delete` / `list_names`, typed errors (`ValidationError`, `NotFoundError`, `HiddenError`, `StateError`). Mutations run under a single `LOCK_EX` for the full read-mutate-atomic-write cycle.
- `shushu.cli._errors` — `ShushuError` + exit-code constants.
- `shushu.cli._output` — `emit_result` / `emit_error` / `emit_warning` with text-vs-JSON discipline.
- CLI parser skeleton: `shushu --help` lists all 12 verbs (doctor, learn, explain, overview, set, show, get, env, run, generate, list, delete); dispatch routes to stub handlers that raise `NotImplementedError` (replaced by Tasks 15-25).

### Security / correctness

- Error classes (`PrivilegeError`, `ShushuError`) pass only `message` to `super().__init__()` so `str(exc)` stays human-readable. `remediation` lives as an attribute. B042 silenced locally with a rationale comment.
- `store.py` rejects `schema_version` that is missing, non-integer, or wrong-valued with distinct error messages instead of a single misleading one.
- `store.py` datetime parse errors name the expected canonical wire format (`YYYY-MM-DDTHH:MM:SSZ`) instead of echoing the cryptic `strptime` traceback.

## [0.2.0] — 2026-04-24

### Added

- v1 design spec (`docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md`).
- v1 implementation plan (`docs/superpowers/plans/2026-04-24-shushu-secrets-cli-v1.md`).
- `CHANGELOG.md`, `.markdownlint-cli2.yaml`, `scripts/lint-md.sh`.
- Vendored `.claude/skills/version-bump/` from afi-cli (adapted for src-layout + `importlib.metadata`).
- CI workflows mirrored from zehut: `tests.yml`, `publish.yml`, `security-checks.yml`, `Dockerfile.integration`.
- Stub `docs/{threat-model,testing,rubric-mapping}.md` (full content lands in later PR).
- `.flake8` with `max-line-length=100` and `per-file-ignores` for `tests/*:S101`.
- `pytest` `integration` marker.

### Changed

- Python floor bumped to `>=3.12` (parity with zehut).
- `__version__` now sourced from `importlib.metadata.version("shushu")` — single source of truth in `pyproject.toml`.
- `src/shushu/cli.py` split into `src/shushu/cli/` package with `_commands/` subdir (no behavior change).
- Dev dependencies moved to PEP 735 `[dependency-groups].dev` so `uv sync` installs them by default; added `pytest-xdist`, `pylint`, `bandit`, `flake8-bandit`, `flake8-bugbear`, `coverage`, `pre-commit`.
- `.claude/skills/version-bump/scripts/bump.py`: drop unused `__init__.py` literal-patching path; `update_changelog()` now preserves the `[Unreleased]` header instead of pushing it down the file.

### Fixed

- CI jobs `lint` / `unit` / `integration` previously failed because dev tools weren't installed under `[project.optional-dependencies]`.

## [0.1.0] — 2026-04-24

- Initial scaffold.
