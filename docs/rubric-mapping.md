# shushu afi-rubric mapping

Per-verb reference for shushu's 12 CLI verbs: purpose, exit codes,
and the structured JSON success payload. shushu follows the
[afi-cli](https://github.com/agentculture/afi-cli) rubric for
agent-first CLIs (noun-verb shape, structured `--json` output, exit
codes from sysexits.h with named constants).

## Exit codes (the `EXIT_*` constants)

| Code | Name | Meaning |
|---|---|---|
| 0 | `EXIT_SUCCESS` | OK |
| 64 | `EXIT_USER_ERROR` | Bad input from the caller — invalid flag, malformed value, missing record, refused (e.g. hidden), unknown topic |
| 65 | `EXIT_STATE` | Store on disk is corrupt or in an unexpected state |
| 66 | `EXIT_PRIVILEGE` | This operation requires root and the process is not root |
| 67 | `EXIT_BACKEND` | Backend dependency failed (unknown OS user, child process died abnormally) |
| 70 | `EXIT_INTERNAL` | Bug in shushu — file an issue |

Every error path emits a structured ShushuError with a remediation
string that points the user at the next step.

## JSON success envelope

All `--json` outputs are wrapped in `{"ok": true, ...}` for success and
`{"ok": false, "error": {...}}` for errors. The per-verb payloads below
list the keys that appear inside the `ok: true` envelope.

---

## Globals

### learn

Print the agent-authored summary of every verb + concept.

- `0` — always.

JSON:

```json
{"ok": true, "verbs": ["delete", "doctor", ...], "descriptions": {"set": "...", ...}, "concepts": ["..."]}
```

### explain `<topic>`

Print short markdown docs for a verb or concept (e.g. `hidden`,
`admin`, `alert_at`).

- `0` on known topic.
- `64` on unknown topic — remediation lists the canonical topic set.

JSON: not applicable (text output is markdown).

### doctor

Read-only setup / permission / schema integrity checks.

- `0` if no FAIL checks.
- `65` (`EXIT_STATE`) if any FAIL check.
- `66` (`EXIT_PRIVILEGE`) if `--user` / `--all-users` is passed
  without root.
- `67` (`EXIT_BACKEND`) if `--user NAME` resolves to an unknown OS
  user.

JSON success:

```json
{
  "ok": true,
  "checks": [{"name": "store_dir", "status": "PASS", "detail": "..."}, ...],
  "summary": {"pass": 2, "warn": 0, "fail": 0}
}
```

`--all-users` adds a `users` outer array with one entry per
inspected user.

### overview

Rich metadata snapshot with alert classification (`ok` / `alerting` /
`expired`). Never includes `value`.

- `0` always (empty store is fine).
- `64` if user-supplied flags are invalid.

JSON success:

```json
{"ok": true, "secrets": [{"name": "FOO", "hidden": false, "source": "localhost",
                          "purpose": "...", "alert_state": "ok", ...}, ...]}
```

`--all-users` outer shape: `{"ok": true, "users": [{"user": "...", "secrets": [...]}, ...]}`.

---

## Write surface

### set `NAME [VALUE] [flags]`

With `VALUE`: create or update. Without `VALUE`: metadata-only update.
Use `-` for `VALUE` to read from stdin (preferred for real secrets).

- `0` on success (record stored or metadata updated).
- `64` on bad input: invalid name, invalid `--alert-at`, immutable
  field change attempt, `--source admin:*` from non-admin path.
- `66` on `--user` from non-root.

JSON success:

```json
{"ok": true, "name": "FOO", "hidden": false, "updated_at": "2026-04-25T12:34:56Z"}
```

### generate `NAME [--bytes N] [--encoding hex|base64] [flags]`

Random secret. Default 32 bytes hex. `--hidden` never prints the
value.

- `0` on success.
- `64` on invalid `--bytes`, invalid `--encoding`, or invalid
  `--alert-at`.

JSON success (visible):

```json
{"ok": true, "name": "FOO", "hidden": false, "encoding": "hex", "bytes": 32, "value": "..."}
```

JSON success (hidden — `value` field is absent):

```json
{"ok": true, "name": "FOO", "hidden": true, "encoding": "hex", "bytes": 32}
```

### delete `NAME`

Remove a secret.

- `0` on success.
- `64` if `NAME` does not exist.

JSON success:

```json
{"ok": true, "name": "FOO", "deleted": true}
```

---

## Read surface

### show `NAME [--json]`

Print metadata for a secret. **Never** prints `value`.

- `0` on success.
- `64` if `NAME` does not exist.

JSON success:

```json
{"ok": true, "name": "FOO", "hidden": false, "source": "localhost",
 "purpose": "...", "rotation_howto": "...", "alert_at": null,
 "handed_over_by": null,
 "created_at": "2026-04-25T12:34:56Z",
 "updated_at": "2026-04-25T12:34:56Z"}
```

### get `NAME`

Print value to stdout. **Refused if hidden.** Deliberately does NOT
register `--user` / `--all-users` — admin cannot extract values via
the CLI (H2 contract). For plaintext as root, use `sudo cat`.

- `0` on success.
- `64` if `NAME` does not exist OR is hidden (remediation points at
  `shushu run --inject`).

JSON success:

```json
{"ok": true, "name": "FOO", "value": "..."}
```

### env `NAME1 [NAME2 ...]`

POSIX-quoted `export` lines for `eval $(shushu env A B)`. **Refuses
the whole call** if any named secret is hidden. Like `get`, no admin
flags.

- `0` on success.
- `64` if any `NAME` does not exist OR is hidden.

Output is shell text, not JSON:

```sh
export FOO='value'
export BAR='other value'
```

### run `--inject VAR=NAME [...] -- cmd [args]`

Fork-exec via `os.execvpe` with the secret stamped into env as `VAR`.
**Both visible and hidden secrets allowed** — `run --inject` is the
ONLY consumer for hidden secrets. Last-wins on duplicate VAR. No
admin flags.

- `0` from the child if the child returned `0`; otherwise the child's
  exit code.
- `64` on malformed `--inject` (missing `=`, empty VAR, empty NAME),
  unknown secret name, missing `--`, or command not found.

Output is whatever the child wrote to stdout/stderr.

### list

Names only, sorted, one per line.

- `0` always.

JSON success:

```json
{"ok": true, "names": ["BAR", "FOO"]}
```

`--all-users` outer shape: `{"ok": true, "users": [{"user": "...", "names": [...]}, ...]}`.

---

## Admin verbs (`--user` / `--all-users`)

Admin verbs route through `setuid-fork`
(`shushu.privilege.run_as_user` plus `shushu.admin.as_user`). The
fork-child runs as the target user, sets `HOME` correctly, and
translates `ShushuError` + `store.*` exceptions to the standard exit
codes via `cli._translate.translate_errors`.

`get`, `env`, `run` are deliberately admin-flag-free. The H2
hidden-secret contract is preserved: admin (including root) cannot
extract a value through any CLI verb.

| Verb | `--user` | `--all-users` | Why |
|---|---|---|---|
| `set`     | yes | — | write only into one user's store |
| `generate`| yes | — | write only into one user's store |
| `show`    | yes | — | metadata-only read of one user |
| `delete`  | yes | — | write only into one user's store |
| `list`    | yes | yes | enumerate names |
| `overview`| yes | yes | enumerate metadata |
| `doctor`  | yes | yes | check store integrity per user |
| `get`     | no  | no | values not extractable via CLI |
| `env`     | no  | no | values not extractable via CLI |
| `run`     | no  | no | exec-side; admin uses the verb under sudo if needed |
| `learn`   | no  | no | static documentation |
| `explain` | no  | no | static documentation |
