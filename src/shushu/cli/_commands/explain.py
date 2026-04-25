"""`shushu explain <topic>` — short markdown docs per topic."""

from __future__ import annotations

from shushu.cli._errors import EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result

_TOPICS = {
    "set": (
        "`shushu set NAME [value] [--flags]`\n\n"
        "Create or update. With value: writes value + metadata. Without value: updates mutable"
        " metadata only (`--purpose`, `--rotate-howto`, `--alert-at`). `source` and `hidden`"
        " are immutable post-create. Use `-` for value to read from stdin (preferred for real"
        " secrets)."
    ),
    "show": (
        "`shushu show NAME [--json]`\n\n"
        "Print metadata (name, source, purpose, rotation_howto, alert_at, hidden,"
        " handed_over_by, timestamps). Never prints `value`."
    ),
    "get": (
        "`shushu get NAME`\n\n"
        "Print value to stdout. Refuses if the secret is hidden"
        " (use `shushu run --inject`)."
    ),
    "env": (
        "`shushu env NAME1 [NAME2 ...]`\n\n"
        "Print POSIX shell export lines for `eval $(shushu env FOO BAR)`."
        " Refuses if any named secret is hidden."
    ),
    "run": (
        "`shushu run --inject VAR=NAME [--inject ...] -- cmd [args...]`\n\n"
        "Fork, set env vars from the store, `execvp` the command."
        " Works for hidden and non-hidden."
    ),
    "generate": (
        "`shushu generate NAME [--bytes N] [--encoding hex|base64] [flags]`\n\n"
        "Create a random secret. Defaults to 32 bytes hex."
        " `--hidden` → never prints value."
    ),
    "list": (
        "`shushu list [--json] [--user NAME|--all-users]`\n\n"
        "Names only, one per line. Scriptable."
    ),
    "delete": "`shushu delete NAME`\n\nRemove a secret. No undo.",
    "overview": (
        "`shushu overview [--json] [--expired] [--user NAME|--all-users]`\n\n"
        "Rich metadata snapshot with alert classification."
    ),
    "doctor": (
        "`shushu doctor [--json] [--user NAME|--all-users]`\n\n"
        "Verify store dir, file modes, schema_version, and per-record validity."
    ),
    "hidden": (
        "A *hidden* secret has `hidden: true`. It is immutable — you cannot toggle it."
        " The CLI refuses to print its value via `get` or `env`; only `shushu run --inject`"
        " can consume it. Note: the file is still plaintext on disk (mode 0600)."
        " `hidden` is a CLI contract, not cryptography."
    ),
    "admin": (
        "Admin mode is `sudo shushu <verb> --user NAME` (or `--all-users` for reads)."
        " shushu forks, drops to the target user's uid/gid, then writes as that user."
        " The target user owns the resulting file. Admin *cannot* read values through the CLI"
        " — even for root. Use `sudo cat` for plaintext."
    ),
    "alert_at": (
        "Optional ISO date (`YYYY-MM-DD`). `overview` classifies records as ok /"
        " alerting (within 30 days) / expired."
        " shushu never enforces expiry — the date is informational."
    ),
}


def handle(args) -> int:
    topic = args.topic
    body = _TOPICS.get(topic)
    if body is None:
        raise ShushuError(
            EXIT_USER_ERROR,
            f"no topic {topic!r}",
            "try: shushu explain set | hidden | admin | alert_at (or any verb name)",
        )
    emit_result(body, json_mode=False)
    return 0
