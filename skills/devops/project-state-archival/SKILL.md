---
name: project-state-archival
description: "Archive project state to GitHub, then clear local workspace."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [archival, git, worktree, cleanup, backup, github, teardown]
    related_skills: [git-push-troubleshooting, github-repo-management, git-essentials]
---

# Project State Archival — push state, then clear local workspace

When the user shifts focus away from one/more projects and asks to "make sure
projects with their states are uploaded to GitHub, then clear them locally",
do this in a strict order. The failure mode that loses real work is deleting
before every branch and every untracked-but-valuable file is safely on a remote.

## Golden rule
Never delete a local repo/dir until you have PROVEN, per-project, that every
branch is on its origin AND every untracked-but-valuable file is preserved
somewhere durable. Deletion is the LAST step, after an explicit confirmation.

## 1. Enumerate everything first
- `find <workspace> -maxdepth 3 -name ".git" -type d` — git repos (directory).
- `.git` that is a FILE (content `gitdir: <path>`) = a **git worktree**, not a
  standalone repo. Its branches live in the parent repo's object store but are
  checked out in a separate directory. You MUST also enumerate these; they are
  easy to miss and can hold unpushed work.
- Note non-git dirs too (test artifacts, venvs, handoff notes, reports).

## 2. Verify EVERY branch is pushed (the big pitfall)
For each repo, per branch:
```bash
git fetch origin
git rev-list --count origin/<branch>..<branch>   # >0 = unpushed commits
git status --porcelain                            # untracked files
```
**Pitfall:** `git status` on the main checkout does NOT see worktree branches.
`git log --branches --not --remotes` on the parent may also miss them or the
count can be stale until you `git fetch`. The reliable check is the
`rev-list --count origin/<branch>..<branch>` loop, after a fresh fetch, for
EVERY local branch INCLUDING worktree branches. In practice this caught
`m14/form-field-ap` (3 commits ahead) and `m14/freetext-ap` (2 ahead) that the
initial `status`/`log` sweep reported clean. Always re-run the per-branch count
after the fetch and after pushes — refs change under you.
Push any that are behind: `git push origin <branch>`.

There is a runnable version of this check in the skill:
`scripts/check-pushed.sh <repo-dir> [remote]` — fetches, per-branch-counts
against the remote for every local branch (worktrees included), and flags
untracked files. Run it over every repo before deleting anything.

## 3. Find untracked-but-valuable files BEFORE deletion
`git status --porcelain | grep '^??'` per repo. Common culprits:
- AI-index files that were never committed (`AGENTS.md`, `MODULES.md`, `REPO_MAP.md`
  left as local index) — these are real state, not noise.
- Reports, handoff/notes docs sitting at the workspace root, not in any repo.
- A repo whose PARENT dir is not itself a git repo (e.g. `playground/results-repo`
  is a repo, but the surrounding `playground/` cluster source is tracked nowhere).

## 4. Secret scan before ANY push (user requirement: no secrets/private files)
- Grep the to-be-pushed source for hardcoded keys:
  `grep -rniE 'api_key|secret|token|password|BEGIN (RSA|OPENSSH|PRIVATE)|ghp_|gho_|sk-[a-z0-9]'`.
  Legit hits are `os.getenv("KEY")` and docs — confirm, don't assume.
- Verify `.env`, `.venv/`, `data/*.db`, `*.pem`, `*.key` are gitignored and NOT
  staged. `git check-ignore .env .venv/ data/` should return them.
- If any real secret is found, exclude it / scrub before pushing. Never push
  `.env` or private keys under any circumstance.

## 5. Preserve untracked state into a kept sibling
Before deleting, copy untracked-but-valuable files into a `preserved/` dir under
a project that is being KEPT (or into the results repo). Example layout:
```
kept-project/preserved/libreoffice-core-index/{AGENTS.md,MODULES.md,REPO_MAP.md}
kept-project/preserved/handoff/to-rosetta.md
kept-project/preserved/upstream-integration-report.md
```
Then delete the original copies/dirs.

## 6. Check dependencies before deleting (keep cluster runnable?)
Ask/clarify scope: a kept project often DEPENDS on dirs you plan to delete (e.g.
a kept agno cluster needs `libreoffice-core` + `lo-writer` via its config's
`LO_REPO`). Deleting those makes the kept code non-runnable. Surface this
trade-off explicitly and let the user choose: clear the deps too (re-cloneable)
vs keep the full setup runnable.

## 7. Delete only after confirmation, then verify
- `rm -rf` worktree dirs and repos; keep the kept project, venv, workspace docs.
- Confirm with the user before the destructive `rm -rf` batch.
- Report disk freed (`df -h /`).

## 8. Deliverable summary table
Report a table of: project → GitHub remote → branches verified pushed → kept or
cleared. Then a short self-critique (SPOFs / what's now-only-local / dangling
cron jobs referencing deleted paths).

## Pitfalls recap
- Worktree branches invisible to main-checkout `status` — enumerate worktrees,
  per-branch `rev-list --count` after `fetch`.
- Re-fetch and re-count after pushing; refs change.
- Untracked AI-index files and root-level docs are real state — preserve first.
- Repo-in-repo: a repo's parent dir may be tracked nowhere; audit the parent.
- Secret scan before push; gitignore discipline for `.env`/keys/dbs.
- Deleting a kept project's dependencies silently breaks it — ask first.
