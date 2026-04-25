"""`shushu learn` — agent-authored self-teaching output."""

from __future__ import annotations

from shushu.cli._output import emit_result

_VERBS = {
    "set": (
        "Create or update a secret. With value: writes value + metadata."
        " Without value: updates mutable metadata only."
    ),
    "show": "Print full metadata for a secret (never value).",
    "get": "Print value to stdout. Refused if hidden.",
    "env": "Emit shell export lines for eval. Refused if any named secret is hidden.",
    "run": "Spawn a command with secrets injected as env vars. Works for hidden and non-hidden.",
    "generate": "Create a random secret (hex or base64). --hidden hides value from print.",
    "list": "Names only, one per line. Scriptable.",
    "delete": "Remove a secret.",
    "overview": "Rich metadata snapshot; alert classification; --expired filter.",
    "doctor": "Setup / permission / schema integrity checks.",
    "learn": "What you are reading.",
    "explain": "Human-readable docs for a verb or concept (e.g. `shushu explain hidden`).",
}

_CONCEPTS = [
    "Hidden secrets can only be consumed via `shushu run --inject`. get/env refuse them.",
    (
        "Admin mode: `sudo shushu <verb> --user <name>` writes into another user's store"
        " via setuid-fork."
    ),
    "The CLI never prints values in admin mode — even for root. Use `sudo cat` for plaintext.",
    "Every destructive op is silent-overwrite; there is no rollback in v1.",
    "alert_at is informational — shushu never deletes or refuses based on it.",
]


def _format_text() -> str:
    lines = [
        "# shushu — agent-first per-OS-user secrets manager",
        "",
        "## Verbs",
    ]
    for verb in sorted(_VERBS):
        lines.append(f"- `{verb}` — {_VERBS[verb]}")
    lines.append("")
    lines.append("## Concepts")
    for concept in _CONCEPTS:
        lines.append(f"- {concept}")
    return "\n".join(lines)


def handle(args) -> int:
    if args.json:
        payload = {
            "verbs": sorted(_VERBS.keys()),
            "descriptions": _VERBS,
            "concepts": _CONCEPTS,
        }
        emit_result(payload, json_mode=True)
    else:
        emit_result(_format_text(), json_mode=False)
    return 0
