# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`shushu` is an early-stage **uv-managed Python CLI**. The scaffold is intentionally minimal — argparse-based entry point, no runtime dependencies yet. Expect this file to grow as the CLI's actual purpose and subcommands are added.

Remote: `https://github.com/OriNachum/shushu`

## Layout

```text
src/shushu/          # package (src-layout)
  __init__.py        # exports __version__
  __main__.py        # enables `python -m shushu`
  cli.py             # argparse entry point — main() is the console_script target
tests/               # pytest suite
pyproject.toml       # hatchling build; [project.scripts] shushu = shushu.cli:main
```

The console script **`shushu`** is registered in `pyproject.toml` and resolves to `shushu.cli:main`. Keep that wiring intact when refactoring — the CLI is the product.

## Common commands

```bash
uv venv                         # create .venv
uv pip install -e ".[dev]"      # editable install with dev extras
uv run shushu --version         # smoke-test the installed entry point
uv run pytest                   # run the full suite
uv run pytest tests/test_cli.py::test_version_flag   # run a single test
uv run pytest -k version        # run tests matching an expression
```

## Lint / format

Dev extras include `black`, `isort`, and `flake8`. Config (line length 100, py310 target) lives in `pyproject.toml`.

```bash
uv run black src tests
uv run isort src tests
uv run flake8 src tests
```

## Version discipline

Version is declared in **two places that must stay in sync**:

- `pyproject.toml` → `[project].version`
- `src/shushu/__init__.py` → `__version__`

`cli.py` reads `__version__` from the package and surfaces it via `--version`, and `test_default_prints_version` asserts the two agree. Bump both together.

## Python version

`requires-python = ">=3.10"`. `cli.py` uses PEP 604 union syntax (`Sequence[str] | None`) and `from __future__ import annotations` — don't lower the floor without revisiting those.
