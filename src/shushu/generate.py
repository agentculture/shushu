"""Random secret generation.

Wraps `secrets.token_bytes` with hex/base64 encoding. No crypto policy
decisions beyond picking a sensible default size (32 bytes — 256 bits).
"""

from __future__ import annotations

import base64
import secrets as _secrets
from typing import Literal

Encoding = Literal["hex", "base64"]
DEFAULT_BYTES = 32
DEFAULT_ENCODING: Encoding = "hex"


def random_secret(nbytes: int = DEFAULT_BYTES, encoding: Encoding = DEFAULT_ENCODING) -> str:
    if nbytes <= 0:
        raise ValueError(f"nbytes must be positive, got {nbytes}")
    raw = _secrets.token_bytes(nbytes)
    if encoding == "hex":
        return raw.hex()
    if encoding == "base64":
        return base64.b64encode(raw).decode("ascii")
    raise ValueError(f"unknown encoding: {encoding!r} (expected 'hex' or 'base64')")
