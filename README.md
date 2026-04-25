# shushu

Agent-first per-OS-user secrets manager CLI. Part of the
[AgentCulture](https://github.com/agentculture) ecosystem; sibling to
[`zehut`](https://github.com/agentculture/zehut) (identity layer) and
patterned on [`afi-cli`](https://github.com/agentculture/afi-cli)
(noun-verb shape, exit-code discipline, structured `--json` output).

Each OS user gets their own secrets store at
`~/.local/share/shushu/secrets.json` (mode `0600`, owned by the
user). shushu never reaches across users in self-mode. Admin handoff
to another user goes through a single `setuid-fork` chokepoint and
preserves the H2 hidden-secret contract — admin can never extract a
value through any CLI verb.

## Install

```bash
uv tool install shushu
shushu --version
```

Linux only (uses `setuid` / `useradd` semantics). Python ≥ 3.12.

## Quick start

```bash
# store a secret you already have (stdin form preferred — keeps the
# value out of /proc/<pid>/cmdline and shell history)
echo -n "sk-..." | shushu set OPENAI_API_KEY -

# generate a random one, hidden — never printed
shushu generate JWT_SECRET --bytes 32 --hidden

# inspect (never prints value)
shushu show OPENAI_API_KEY
shushu show OPENAI_API_KEY --json

# consume — visible secrets only
shushu get OPENAI_API_KEY
eval $(shushu env OPENAI_API_KEY DATABASE_URL)

# consume — visible OR hidden (this is the only path for hidden)
shushu run --inject JWT=JWT_SECRET --inject DB=DATABASE_URL -- ./myapp
```

`shushu list` and `shushu overview` give names and metadata.
`shushu delete NAME` removes a record.

## Self-teaching surface

```bash
shushu learn                # markdown summary of every verb + concept
shushu learn --json         # structured payload for agent consumers
shushu explain hidden       # explain a concept
shushu explain set          # explain a verb
```

## Admin handoff

shushu is single-admin-trusted-host. Admin operations go through
`sudo`; the binary forks → drops to the target user → writes/reads
under their uid. Every admin write stamps `source = "admin:<invoker>"`
and `handed_over_by = "<invoker>"` so the receiving user can audit.

```bash
# provision a secret into alice's store as root
sudo shushu set --user alice OPENAI_API_KEY -

# read-only audit across every user with a shushu store
sudo shushu overview --all-users
sudo shushu doctor --all-users

# delete a record from alice's store
sudo shushu delete --user alice OPENAI_API_KEY
```

`get`, `env`, `run` deliberately have NO admin flags — values are
never extractable through the CLI, even for root. Use `sudo cat
~alice/.local/share/shushu/secrets.json` if you truly need plaintext
(at which point you've moved outside shushu's contract).

## Hidden secrets — the H2 contract

A secret with `hidden: true`:

- Is **immutable post-create** — you cannot toggle the hidden flag.
- Is **refused** by `get`, `env`, `show` (they exit `64` with a
  remediation pointing at `run --inject`).
- Has its value **omitted** from `generate --hidden --json` output
  (the JSON payload has no `value` field).
- Is consumable **only** through `shushu run --inject VAR=NAME -- cmd`.

Hidden is a CLI contract, not encryption. The on-disk file is
plaintext at `0600`. Encryption-at-rest is tracked for v2.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `64` | bad input from the caller (invalid flag, missing record, hidden refusal, etc.) |
| `65` | store is corrupt / schema mismatch / unreadable |
| `66` | this operation requires root |
| `67` | backend dependency failed (unknown OS user, etc.) |
| `70` | bug in shushu — please file an issue |

Every error path emits a structured `ShushuError` with a remediation
string. With `--json`, errors land as `{"ok": false, "error": {...}}`
on stdout (single-payload contract).

## Docs

- [Design spec](docs/superpowers/specs/2026-04-24-shushu-secrets-cli-design.md)
- [Threat model](docs/threat-model.md)
- [Per-verb rubric mapping](docs/rubric-mapping.md)
- [Testing notes](docs/testing.md)
- [CHANGELOG](CHANGELOG.md)

## Development

```bash
git clone https://github.com/agentculture/shushu
cd shushu
uv sync                                                         # install deps
bash .claude/skills/run-tests/scripts/test.sh -p                # unit suite
bash .claude/skills/run-tests/scripts/test.sh --ci              # CI parity
```

Integration tests need real root + `useradd`/`userdel`, which we
only do inside a disposable Docker image:

```bash
docker build -f .github/workflows/Dockerfile.integration -t shushu-int .
docker run --rm -e SHUSHU_DOCKER=1 shushu-int uv run pytest tests/integration -v
```

See [docs/testing.md](docs/testing.md) for the broader test-isolation
conventions and the smoke-test namespace under `/tmp/shushu-tests/`.

## License

MIT. © 2026 Ori Nachum / AgentCulture.
