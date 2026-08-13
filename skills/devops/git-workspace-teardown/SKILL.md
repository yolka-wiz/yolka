---
name: git-workspace-teardown
description: "Back up project state to GitHub, then clear local clones."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [git, backup, teardown, cleanup, worktree, github, secrets, verify]
    related_skills: [github-repo-management, git-secret-purge, git-essentials]
---

# Git Workspace Teardown

Use when the user asks to move focus away from a set of projects: "upload/back
up projects with their state to GitHub, then clear them locally." The deliverable
is ZERO net state loss — every commit, branch, and untracked-but-valuable file is
safely on a remote (or explicitly preserved) BEFORE any local deletion happens.

## Golden rule

**Never delete a local repo until you can prove, per-branch and per-file, that
nothing would be lost.** Delete only after verification, then re-verify the
deletion freed what was expected and the kept workspace is intact.

## Workflow

1. **Enumerate everything** — don't assume a flat repo layout.
   ```bash
   find . -maxdepth 3 -name .git -type d          # real repos
   git worktree list                              # in each repo: linked worktrees
   ```
   Worktrees are the #1 blind spot — their `.git` is a *file* pointing into a
   parent repo's `worktrees/` dir, so a flat `.git -type d` find misses them.

2. **Per-repo state check** — for each repo: remotes, current branch, porcelain
   status, and per-branch push state. The aggregated `git log --branches --not
   --remotes` is NOT sufficient — it can miss worktree branches right after a
   fetch. Verify each branch explicitly:
   ```bash
   git fetch origin
   for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
     echo "$b: $(git rev-list --count origin/$b..$b) unpushed"   # 0 = safe
   done
   ```

3. **Find untracked-but-valuable files** (`git status --porcelain | grep '^??'`).
   Common culprits that are NOT on any remote: generated AI-index files
   (`AGENTS.md`, `MODULES.md`, `REPO_MAP.md`), handoff/notes, research reports.
   Preserve them into a kept directory (e.g. `project/preserved/`) before clearing
   the clone they live in. Call these out explicitly — they're invisible to git.

4. **Secret-scan before any push.** Verify `.env`, `.venv/`, `data/*.db`,
   `*.pem`, `*.key` are gitignored and NOT being staged. Grep source for
   hardcoded keys:
   ```bash
   grep -rniE '(api_key|secret|token|password|ctx7sk|sk-[a-z0-9]|BEGIN (RSA|OPENSSH|PRIVATE)|ghp_|gho_)' \
     --include='*.py' --include='*.go' --include='*.sh' --include='*.md' . \
     | grep -vE '\.venv/|\.env:|example|Never commit|os\.getenv'
   ```
   A clean scan (only `os.getenv(...)` refs and docs) means it's safe to push.

5. **Push what's ahead, re-verify 0 unpushed everywhere**, THEN delete.

6. **Delete, then confirm.** Report what was freed and that kept items (venv,
   active project dirs) are intact. State which kept items are now the SINGLE
   local copy — that's a risk the user should know.

## Pitfalls

- **Worktree branches ahead of origin while `main` is clean.** `git status` on
  the main checkout shows nothing dirty, but linked worktrees can have unpushed
  commits. Check `git worktree list` and verify every branch. This session's
  `m14/*` branches were 2–3 commits ahead and would have been lost.
- **Untracked index/notes files are invisible to git** but are real state.
  `AGENTS.md`/`MODULES.md`/`REPO_MAP.md` regenerated for an AI-indexed clone are
  local-only unless preserved.
- **The kept project may depend on what you're deleting.** Before clearing LO
  clones, check whether the kept playground cluster references them (e.g. via
  an env var like `LO_REPO`). Deleting a dependency silently breaks the kept
  project — surface it before deleting.
- **`source ~/.bashrc` on a non-interactive shell may not load PATH.** In this
  environment Go lives at `~/.local/go/bin`; export it explicitly
  (`export PATH="$HOME/.local/go/bin:$PATH"`) rather than relying on sourcing.
- **Don't offer scope menus for an undefined "improve X" task.** When the user
  says "we want to improve it" without direction, ask open-ended or wait for
  them to tell you — do NOT front-load a multi-option clarify. The user drives
  project direction and will say "stop, I'll tell you."

## Verification (before reporting done)

- Every branch shows `0 unpushed` after `git fetch origin`.
- All untracked-but-valuable files copied to a kept location and listed.
- Secret scan clean; no `.env`/keys/DBs staged.
- Deletion target list matches what the user confirmed; kept dirs intact;
  freed space reported via `df -h`.
