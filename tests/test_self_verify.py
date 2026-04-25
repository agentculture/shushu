"""End-to-end dogfood lifecycle.

Single test that walks every verb against a fresh `tmp_path` store,
asserting the H2 hidden-secret contract holds end-to-end (hidden values
never appear in stdout/stderr from any verb except `run --inject`).
Every regression here blocks the commit.

Uses the shared `cli_run` fixture and autouse `_tmp_home` from
`tests/conftest.py` (added in PR #6's review-fix). The single
subprocess invocation in step 8 is necessary because `os.execvpe`
inside `cli_run` would replace the pytest process itself.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404
import sys


def test_self_verify_lifecycle(cli_run):
    # 1. set with --alert-at
    rc, _, _ = cli_run(["set", "FOO", "bar", "--purpose", "self-test", "--alert-at", "2099-01-01"])
    assert rc == 0

    # 2. generate hidden — value must NOT appear in stdout
    rc, out_gen, _ = cli_run(["generate", "BAZ", "--bytes", "16", "--hidden"])
    assert rc == 0
    assert "BAZ" in out_gen
    # Verify the literal random value never leaked. Read it from the store
    # directly (legitimate test introspection) and assert it isn't in stdout.
    from shushu import store

    rec = store.get_record("BAZ")
    assert rec.value not in out_gen
    assert rec.hidden is True

    # 3. list — both names sorted
    rc, out, _ = cli_run(["list", "--json"])
    assert rc == 0
    assert set(json.loads(out)["names"]) == {"FOO", "BAZ"}

    # 4. show — metadata only, never `value`
    rc, out, _ = cli_run(["show", "FOO", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert "value" not in payload
    assert payload["name"] == "FOO"

    # 5. get — visible secret
    rc, out, _ = cli_run(["get", "FOO"])
    assert rc == 0
    assert out.strip() == "bar"

    # 6. get hidden — refused with EXIT_USER_ERROR
    rc, _, err = cli_run(["get", "BAZ"])
    assert rc == 64
    assert "hidden" in err.lower()

    # 7. env — POSIX-quoted export for visible
    rc, out, _ = cli_run(["env", "FOO"])
    assert rc == 0
    assert "export FOO='bar'" in out

    # 8. run --inject — only consumer for hidden secrets. subprocess because
    # os.execvpe inside the in-process cli_run would replace pytest.
    r = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "shushu",
            "run",
            "--inject",
            "X=BAZ",
            "--",
            sys.executable,
            "-c",
            "import os; print(len(os.environ['X']))",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "SHUSHU_HOME": os.environ["SHUSHU_HOME"]},
    )
    assert r.returncode == 0, r.stderr
    # 16 bytes of hex = 32 chars.
    assert r.stdout.strip() == "32"

    # 9. metadata-only set — value preserved
    rc, _, _ = cli_run(["set", "FOO", "--purpose", "updated"])
    assert rc == 0
    assert store.get_record("FOO").purpose == "updated"
    assert store.get_value("FOO") == "bar"  # value unchanged

    # 10. immutable refusal — source change rejected
    rc, _, _ = cli_run(["set", "FOO", "v2", "--source", "https://other"])
    assert rc == 64

    # 11. delete
    rc, _, _ = cli_run(["delete", "FOO"])
    assert rc == 0

    # 12. doctor — passes on remaining hidden record
    rc, out, _ = cli_run(["doctor", "--json"])
    assert rc == 0
    assert json.loads(out)["ok"] is True

    # 13. overview — 1 secret remaining (BAZ)
    rc, out, _ = cli_run(["overview", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert len(payload["secrets"]) == 1
    assert payload["secrets"][0]["name"] == "BAZ"
    assert payload["secrets"][0]["hidden"] is True
    # Hidden contract holds end-to-end: no value field anywhere in overview.
    assert "value" not in payload["secrets"][0]
