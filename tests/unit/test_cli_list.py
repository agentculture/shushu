from __future__ import annotations

import json

from shushu import store


def test_list_empty_prints_nothing_text(cli_run):
    rc, out, _ = cli_run(["list"])
    assert rc == 0
    assert out == ""


def test_list_names_sorted_one_per_line(cli_run):
    for n in ["C", "A", "B"]:
        store.set_secret(name=n, value="v", hidden=False, source="localhost", purpose="")
    rc, out, _ = cli_run(["list"])
    assert rc == 0
    assert out.splitlines() == ["A", "B", "C"]


def test_list_json(cli_run):
    store.set_secret(name="X", value="v", hidden=False, source="localhost", purpose="")
    rc, out, _ = cli_run(["list", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload == {"ok": True, "names": ["X"]}
