---
name: pr-review
description: >
  Handle PR review feedback for shushu: one-shot status overview,
  fetch comments, reply, resolve threads. Use when: working with PR
  reviews, responding to review comments, resolving threads, or
  checking the comment-pipeline / SonarCloud / Cloudflare Pages
  status of an open PR.
---

# PR Review (shushu)

Project-vendored copy of the PR review workflow. Adds one shushu-specific
script — `pr-status.sh` — on top of the standard `pr-comments` /
`pr-reply` / `pr-batch` triad shipped under `~/.claude/skills/pr-review/`.

## When to use

- **`pr-status.sh`** — every time you want a single-glance picture of an
  open PR: state (open / merged / closed), CI checks, which review bots
  have weighed in, SonarCloud quality-gate verdict, Cloudflare Pages
  deploy preview, and the resolved-vs-unresolved inline-thread tally.
  Call this **first** before triaging — it tells you whether bots have
  even posted yet (saves the dance of waking up too early).
- **`pr-comments.sh`** (under `~/.claude/skills/pr-review/scripts/`) —
  full bodies of every comment, after status looks ready to triage.
- **`pr-reply.sh` / `pr-batch.sh`** — same global location — to reply
  and resolve threads.

## Workflow

### 1. Status (cheap)

```bash
bash .claude/skills/pr-review/scripts/pr-status.sh PR_NUMBER
```

The script returns:

1. **PR header** — number, title, URL, author, branch, state (incl.
   merged-at / merged-by when applicable; `OPEN (draft)` for drafts).
2. **CI checks** — `gh pr checks` formatted with ✅ / ❌ / … / ⏭ icons.
3. **Review pipeline** — per-bot summary:
   - **Copilot** — top-level overview reviews + inline thread count.
   - **qodo** — summary issue-comments + inline thread count.
   - **Cloudflare** — pages.dev deploy URL if posted, else "no deploy
     preview".
   - **SonarCloud** — quality gate (OK / WARN / ERROR), open issue
     count, security hotspot count (all via SonarCloud API, not from
     the PR comment body).
4. **Inline threads** — total, resolved, unresolved tally with bot
   labels for every unresolved thread.

The script exits 0 even if some checks are still pending (so you can
parse it from another script). Exit code is non-zero only on a real
shell error (network failure, malformed JSON).

### 2. Fetch comment bodies

```bash
bash ~/.claude/skills/pr-review/scripts/pr-comments.sh PR_NUMBER
```

Returns full bodies for every inline thread, issue comment, and
top-level review (Copilot overviews etc.).

### 3. Triage

For each comment, decide:

- **FIX** — valid concern, make the code change.
- **PUSHBACK** — disagree, explain why in the reply. shushu has two
  recurring pushbacks already documented in
  `feedback_review_pushbacks.md` memory: qodo's "dynamic `__version__`"
  rule violation, and SonarCloud's `docker:S6471` (`USER root` in the
  integration Dockerfile, currently inactive).

### 4. Fix + reply + resolve

Make changes, commit, push, then batch-reply:

```bash
bash ~/.claude/skills/pr-review/scripts/pr-batch.sh --resolve PR_NUMBER <<'EOF'
{"comment_id": 123, "body": "Fixed in <sha> -- ..."}
{"comment_id": 456, "body": "PUSHBACK -- ..."}
EOF
```

Single thread:

```bash
bash ~/.claude/skills/pr-review/scripts/pr-reply.sh --resolve PR_NUMBER COMMENT_ID "Fixed in <sha>"
```

## Scripts

### pr-status.sh (shushu-specific)

```bash
bash .claude/skills/pr-review/scripts/pr-status.sh [--repo OWNER/REPO] [--sonar-key KEY] PR_NUMBER
```

| Flag | Default | Description |
|------|---------|-------------|
| `--repo OWNER/REPO` | from `gh repo view` | Override repo |
| `--sonar-key KEY` | `<owner>_<name>` | SonarCloud project key |
| `PR_NUMBER` | — | required |

Requires `gh`, `jq`, `curl`, `python3`. `gh` must be authenticated.

The SonarCloud API is hit anonymously (public projects only). For private
projects, `curl` would need a `SONAR_TOKEN`; not implemented yet.

### pr-comments.sh, pr-reply.sh, pr-batch.sh

Live at `~/.claude/skills/pr-review/scripts/`. The shushu-local
`pr-status.sh` does NOT shadow them — call them by their global path.

## Branch hygiene

If the current branch already has an open PR, **do not** add unrelated
commits. Branch off `main`, push, open a separate PR. Only add commits
to an existing PR's branch if they belong to that PR's scope.

## Notes

- All scripts auto-detect `owner/repo` from the current git repo.
- Replies are auto-signed with `\n\n- Claude` per global CLAUDE.md.
- Thread resolution uses GitHub GraphQL API (REST doesn't support it).
- The shushu repo's `feedback_review_pushbacks.md` memory carries the
  recurring pushback rationales — consult it before crafting a
  PUSHBACK reply, so the wording stays consistent across PRs.
