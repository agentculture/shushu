from __future__ import annotations

import base64

import pytest

from shushu import generate


def test_hex_default_length_is_64_chars_for_32_bytes():
    s = generate.random_secret(nbytes=32, encoding="hex")
    assert len(s) == 64
    int(s, 16)  # must be valid hex


def test_base64_round_trips():
    s = generate.random_secret(nbytes=32, encoding="base64")
    decoded = base64.b64decode(s, validate=True)
    assert len(decoded) == 32


def test_rejects_unknown_encoding():
    with pytest.raises(ValueError):
        generate.random_secret(nbytes=16, encoding="morse")


@pytest.mark.parametrize("n", [1, 8, 16, 32, 64])
def test_variable_byte_lengths(n):
    s = generate.random_secret(nbytes=n, encoding="hex")
    assert len(s) == n * 2


def test_rejects_zero_or_negative_bytes():
    for n in (0, -1):
        with pytest.raises(ValueError):
            generate.random_secret(nbytes=n, encoding="hex")
