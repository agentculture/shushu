from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout

from shushu.cli import main


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_learn_text_mentions_every_verb():
    rc, out, _ = _run(["learn"])
    assert rc == 0
    expected = [
        "set",
        "show",
        "get",
        "env",
        "run",
        "generate",
        "list",
        "delete",
        "overview",
        "doctor",
    ]
    for verb in expected:
        assert verb in out


def test_learn_json_returns_ok_true_and_verb_index():
    rc, out, _ = _run(["learn", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert "verbs" in payload
    required = {
        "set",
        "show",
        "get",
        "env",
        "run",
        "generate",
        "list",
        "delete",
        "overview",
        "doctor",
    }
    assert set(payload["verbs"]) >= required


def test_explain_known_verb_returns_markdown():
    rc, out, _ = _run(["explain", "set"])
    assert rc == 0
    assert "set" in out.lower()


def test_explain_known_concept():
    rc, out, _ = _run(["explain", "hidden"])
    assert rc == 0
    assert "hidden" in out.lower()


def test_explain_unknown_topic_is_user_error():
    rc, _, err = _run(["explain", "definitely-not-a-topic"])
    assert rc == 64
    assert "definitely-not-a-topic" in err
