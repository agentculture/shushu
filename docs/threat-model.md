# shushu threat model

This document expands §8 of the design spec
([2026-04-24-shushu-secrets-cli-design.md](superpowers/specs/2026-04-24-shushu-secrets-cli-design.md))
into a full threat-model statement: trust boundary, adversary model,
risk surfaces, and residual risks.

## Trust boundary

The host OS filesystem and uid model.
`~/.local/share/shushu/secrets.json` (mode `0600`, owned by the user)
is protected by exactly the same mechanisms that protect
`~/.ssh/id_rsa`. shushu adds **no cryptographic layer on top in v1** —
the H2 "hidden" flag is a CLI contract, not encryption.

The single-admin trusted-host assumption underpins everything.
Multi-tenant hosts, network services, remote attackers, and
hardware-level adversaries are out of scope.

## Adversary model (v1)

The threat actor is a **non-root local user with shell access** on the
same machine. shushu MUST prevent that user from:

1. Reading another user's secrets through shushu.
2. Writing into another user's store through shushu.
3. Forging provenance (`source = "admin:*"`).
4. Extracting another user's plaintext values through any admin verb.
5. Impersonating another user via ambient resolution.

A user with `sudo` is by definition trusted; their actions are out
of the v1 threat scope. Root can already read every file on the
system; shushu cannot meaningfully harden against root.

## Risk surfaces

### 1. setuid-fork handoff

The single chokepoint where uid is changed lives in
`src/shushu/privilege.py::run_as_user`. Order is:

1. `os.setgroups([])` — drop supplementary groups.
2. `os.setgid(user.gid)` and `os.setegid(user.gid)`.
3. `os.setuid(user.uid)` and `os.seteuid(user.uid)`.

Capabilities drop on the `setuid` from euid 0 (no
`SECBIT_KEEP_CAPS`). All return values are checked by the kernel via
the syscalls themselves. TOCTOU between `getpwnam` and `setuid` is
residual on trusted-admin hosts (an admin running `usermod` between
shushu's lookup and fork is the only way to hit it).

The fork-as-target-user wrapper is in `src/shushu/admin.py::as_user`,
which:

- Validates the target via `users.resolve(name)` (raises
  `EXIT_BACKEND` for unknown users).
- Sets `HOME` in the child after the uid drop so `Path.home()`
  resolves correctly.
- Translates ShushuError + `store.*` exceptions inside the child via
  `cli._translate.translate_errors` so admin failures produce the
  same structured exit codes as self-mode.

### 2. File-mode drift

Every write goes through `fs.atomic_write_text`, which sets mode
`0o600` on the temp file before `os.replace`. The store directory is
created with mode `0o700` by `fs.ensure_store_dir`. Drift is
detectable via `shushu doctor` (warns on any non-`0o700` dir or
non-`0o600` file).

### 3. Hidden-secret contract (H2)

CLI contract, not cryptographic. The on-disk file is plaintext at
`0o600`; a user can `cat ~/.local/share/shushu/secrets.json` and
read every hidden value. shushu's `hidden=True` flag enforces:

- `get`, `env`, `show` refuse to print the value (exit 64 with
  remediation pointing at `run --inject`).
- `generate --hidden` never prints the value to stdout or includes
  it in `--json` output.
- `overview` and `list` never expose values regardless of the
  `hidden` flag.
- Admin `--user` / `--all-users` paths inherit all of the above —
  admin can NEVER extract values via the CLI surface, even for root.

The CLI is the contract. Anyone with shell access to the same uid
can read the plaintext. A future v1.x release will add real at-rest
encryption — see the residual-risks table below.

### 4. Admin metadata exfiltration

`overview --all-users` reveals secret **names**, **sources**,
**purposes**, **rotation_howto**, **alert_at**, **handed_over_by**,
and **timestamps** — deliberately, for audit. Values are never
included.

Naming discipline (don't put secrets in name) is outside shushu's
scope. The convention documented in `docs/rubric-mapping.md` and
`shushu explain` is to use env-var-style identifiers.

### 5. Command-line argument leakage

`shushu set FOO bar` writes the literal value `bar` into the
process command line, which is visible in `/proc/<pid>/cmdline` and
in shell history. The recommended form is:

```bash
shushu set FOO -    # read value from stdin
```

`shushu set` documents this in `--help` and the canonical example
in the README leads with the stdin form.

`shushu run --inject VAR=NAME -- cmd` takes only the secret **name**
on the command line; the value is read from the store inside shushu
and stamped into the child's env, never on the command line.

### 6. Input validation

- Names are validated against `^[A-Z_][A-Z0-9_]{0,63}$` in
  `store._validate_name` (compiled as `store.NAME_RE`). Lowercase,
  dashes, dots, and names longer than 64 characters are rejected
  (env-var-unsafe forms); leading `_` is allowed.
- `shushu env` single-quotes values and escapes embedded `'` as
  `'\''` (POSIX-safe). Round-trip through `bash -c` is asserted by
  `test_env_escapes_single_quotes_posix_safe`.
- `shushu run --inject VAR=NAME` parses only `VAR=NAME` shape;
  malformed specs (missing `=`, empty VAR, empty NAME) raise explicit
  per-case `EXIT_USER_ERROR`.

## Residual risks (documented, not mitigated in v1)

| Risk | Mitigation status |
|---|---|
| Plaintext at rest in `secrets.json` | Tracked as the encryption-at-rest issue (see below); v1.x candidate. |
| Root can `cat` any user's secrets directly | CLI surface doesn't expose values via admin verbs; accepted (root is by definition trusted). |
| Orphan stores after user deletion | Not detected in 0.x. `doctor --all-users` enumerates `users.all_users()`, so a store left on disk after the OS user is deleted is invisible. Filesystem-scan-based detection + a cleanup verb deferred to a future v1.x release. |
| setuid-fork TOCTOU with concurrent `usermod` | Accepted on trusted-admin host. |
| Shell-history leakage of literal `set NAME value` | Stdin form (`set NAME -`) is the documented preferred shape; covered in `shushu explain set`. |

## Encryption-at-rest tracking issue

The current 0.x line deliberately ships without on-disk encryption.
The full rationale + candidate approaches (age, libsecret, pass/gpg)
are captured in the tracking issue:

**Issue:** [#8 — v1.x: encryption at rest for secret values](https://github.com/agentculture/shushu/issues/8)

The threat-model assertion that "values are not encrypted at rest"
is a deliberate 0.x choice, not an oversight. A future v1.x release
will add real at-rest encryption with a `schema_version = 2`
migration.
