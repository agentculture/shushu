# Changelog

All notable changes to shushu are recorded here. Entries are kept 1:1
with merged PRs per the per-PR version bump discipline documented in
`CLAUDE.md`.

## [Unreleased]

- (nothing yet — v0.2.0 cut; next bump on the following PR)

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
