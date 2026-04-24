"""shushu — agent-first per-OS-user secrets manager."""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("shushu")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    # Only hit when running from a source tree with no editable install.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
