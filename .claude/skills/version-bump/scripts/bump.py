#!/usr/bin/env python3
"""Bump the version in pyproject.toml and CHANGELOG.md.

Usage:
    bump.py major    # 0.1.0 -> 1.0.0
    bump.py minor    # 0.1.0 -> 0.2.0
    bump.py patch    # 0.1.0 -> 0.1.1
    bump.py show     # print current version

pyproject.toml is the single source of truth for the version. shushu's
`src/shushu/__init__.py` reads it via `importlib.metadata.version()` at
import time, so no literal needs patching there.

Changelog entries are passed via stdin as a JSON object:
    {
      "added": ["New CLI command", "Observer module"],
      "changed": ["Restructured namespace"],
      "fixed": ["WHO reply index bug"]
    }

If no stdin is provided, an empty stub is inserted.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path


def find_pyproject() -> Path:
    """Walk up from cwd to find pyproject.toml."""
    current = Path.cwd()
    while current != current.parent:
        candidate = current / "pyproject.toml"
        if candidate.exists():
            return candidate
        current = current.parent
    print("ERROR: pyproject.toml not found", file=sys.stderr)
    sys.exit(1)


def read_version(path: Path) -> str:
    """Extract version string from pyproject.toml."""
    text = path.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        print("ERROR: version field not found in pyproject.toml", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def bump(version: str, part: str) -> str:
    """Bump the specified part of a semver version."""
    parts = version.split(".")
    if len(parts) != 3:
        print(f"ERROR: version '{version}' is not semver (x.y.z)", file=sys.stderr)
        sys.exit(1)

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        print(f"ERROR: unknown bump type '{part}' (use major, minor, or patch)", file=sys.stderr)
        sys.exit(1)


def write_version(path: Path, old: str, new: str) -> None:
    """Replace old version with new in pyproject.toml."""
    text = path.read_text()
    updated = text.replace(f'version = "{old}"', f'version = "{new}"', 1)
    path.write_text(updated)


def read_changelog_entries() -> dict:
    """Read changelog entries from stdin as JSON."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print("WARNING: could not parse changelog JSON from stdin, using empty stub", file=sys.stderr)
        return {}


def format_changelog_section(new: str, entries: dict) -> str:
    """Format a changelog section from entries dict."""
    today = date.today().isoformat()
    lines = [f"## [{new}] - {today}\n"]

    for section in ("added", "changed", "fixed"):
        items = entries.get(section, [])
        if items:
            lines.append(f"\n### {section.capitalize()}\n")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    # If no entries at all, add empty sections
    if not any(entries.get(s) for s in ("added", "changed", "fixed")):
        lines.append("\n### Added\n")
        lines.append("\n### Changed\n")
        lines.append("\n### Fixed\n")

    return "\n".join(lines) + "\n"


def update_changelog(project_root: Path, new: str, entries: dict) -> None:
    """Insert a new changelog entry into CHANGELOG.md.

    Keeps Keep-a-Changelog structure intact: the [Unreleased] header stays
    at the top as a placeholder for future work, and the new release
    section is inserted right after its body (before the next `## [`
    header, if any). If no [Unreleased] header is found, the entry is
    prepended before the first `## [` header as a fallback.
    """
    changelog = project_root / "CHANGELOG.md"
    if not changelog.exists():
        print("No CHANGELOG.md found — skipping")
        return

    text = changelog.read_text()
    new_entry = format_changelog_section(new, entries)

    unreleased_re = re.compile(r"^## \[Unreleased\].*?$", re.MULTILINE)
    unreleased_match = unreleased_re.search(text)
    if unreleased_match:
        # Find the next "## [" header AFTER the Unreleased one, and insert
        # the new section just before it. If there is no next header,
        # append at end of file.
        next_header = re.search(r"^## \[", text[unreleased_match.end():], re.MULTILINE)
        if next_header:
            insert_at = unreleased_match.end() + next_header.start()
        else:
            insert_at = len(text)
            if not text.endswith("\n"):
                new_entry = "\n" + new_entry
        changelog.write_text(text[:insert_at] + new_entry + text[insert_at:])
        print(f"Updated CHANGELOG.md with [{new}] (preserved Unreleased header)")
        return

    # Fallback: no Unreleased section, prepend before the first release.
    first_release = re.search(r"^## \[", text, re.MULTILINE)
    if first_release:
        changelog.write_text(text[: first_release.start()] + new_entry + text[first_release.start():])
        print(f"Updated CHANGELOG.md with [{new}]")
    else:
        print("WARNING: could not find insertion point in CHANGELOG.md", file=sys.stderr)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    part = sys.argv[1].lower()
    path = find_pyproject()
    current = read_version(path)

    if part == "show":
        print(current)
        sys.exit(0)

    # Read changelog entries before bumping
    entries = read_changelog_entries()

    new = bump(current, part)
    write_version(path, current, new)

    # Update changelog
    update_changelog(path.parent, new, entries)

    print(f"{current} -> {new}")


if __name__ == "__main__":
    main()
