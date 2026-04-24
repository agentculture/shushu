# Changelog

All notable changes to shushu are recorded here. Entries are kept 1:1
with merged PRs per the per-PR version bump discipline documented in
`CLAUDE.md`.

## [Unreleased]

- (nothing yet — v0.3.0 cut; next bump on the following PR)

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
