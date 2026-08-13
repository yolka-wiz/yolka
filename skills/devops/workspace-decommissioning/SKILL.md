---
name: workspace-decommissioning
description: "Use when clearing local projects after backing up to GitHub."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [git, cleanup, backup, github, secrets, worktrees, destructive]
    related_skills: [git-essentials, github-repo-management, git-secret-purge]
---

# Workspace Decommissioning (safe clear)

When the user wants to move focus and "make sure projects are uploaded to
GitHub, then clear them locally." Destructive operation — the whole job is
verifying state is safe BEFORE deleting. Default to read-only audits; get
explicit confirmation of the deletion scope (keep/delete lists) before `rm`.

## Sequence

1. **Inventory** — `ls -la` the workspace; find `.git` dirs AND `.git`
   files (worktrees: `gitdir: <path>` inside). Classify: git repos, git
   worktrees, plain dirs, test artifacts, venvs.
2. **Per-repo state audit** — for each repo:
   - `git remote -v` (know where origin points; some clones point at
     UPSTREAM, not your fork)
   - `git status --porcelain` (dirty? untracked?)
   - `git log --branches --not --remotes --oneline` (unpushed)
   - **`git fetch origin` FIRST, then per-branch
     `git rev-list --count origin/<b>..<b>`** — a single
     `--not --remotes` check can MISS worktree branches with unpushed
     commits (this bit a real cleanup: m14 branches were 2-3 commits ahead).
3. **Push anything unpushed** (worktree branches included) before clearing.
4. **Find untracked-but-valuable files** — AI index files
   (AGENTS.md/MODULES.md/REPO_MAP.md), handoff notes, research reports,
   integration reports. These are NOT in any repo and WILL be lost. Preserve
   them into a kept directory (e.g. `<kept-project>/preserved/`) — 44KB of
   docs beats "oops, deleted".
5. **Secret scan before any push** — `grep -rniE '(api_key|secret|token|
   password|sk-[a-z0-9]|BEGIN (RSA|OPENSSH|PRIVATE)|ghp_|gho_)'` over source
   (exclude `.venv/`, `data/`, `.env`). Confirm `.env` is gitignored in
   every repo (`git check-ignore`). The user's rule: **no secrets or private
   files uploaded, ever** — treat as a hard gate, not a suggestion.
6. **Confirm scope with the user** — present a keep/delete table. If a kept
   project DEPENDS on a to-be-deleted clone (e.g. a cluster that reads
   `libreoffice-core`), surface that dependency and let the user choose.
7. **Delete** — `rm -rf` only confirmed items; keep `agent-env`, venvs,
   `.hermes/`, the kept project, preserved docs.
8. **Verify** — `ls -la` shows only keep-list; preserved files intact;
   `df -h` shows freed space.

## Pitfalls

- **Worktree branches are the #1 data-loss trap** — they live in the main
  repo's `.git/worktrees/`, look "tracked", and are easy to miss in a
  per-repo audit. Check them explicitly.
- **`origin` may be upstream, not your fork** — a clone of `LibreOffice/core`
  can't accept your AI-index files; that's why step 4 (preserve locally)
  exists.
- **Deleting a parent repo orphans its worktrees** — delete worktrees and
  parent together (branches must be pushed first).
- **Re-cloneable vs irreplaceable** — a 1.9GB upstream clone is disposable
  (re-cloneable); a 44KB handoff note is not. Size is not value.
- **Ask before deleting**, even when the user said "clear them locally" —
  the scope (which projects, which kept) has real trade-offs.
- Don't forget: cron jobs / skills referencing deleted paths will break —
  flag them (e.g. a conductor cron pointing at removed clones).

## Verification checklist

- Every repo: 0 unpushed after fetch+push (per branch).
- No secrets in anything pushed; `.env`/`*.pem`/`*.key` gitignored.
- Untracked valuable files copied into a preserved/ dir that survives.
- Deletion scope confirmed in writing with the user.
