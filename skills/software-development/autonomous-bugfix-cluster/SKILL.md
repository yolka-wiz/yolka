---
name: autonomous-bugfix-cluster
description: "Use when running an autonomous bug-fix cluster pipeline."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agents, conductor, bugfix, git, automation, cluster, libreoffice]
    related_skills: [agno-agent-playground, bug-tracker-triage, github-pr-workflow]
---

# Autonomous Bug-Fix Cluster

Drive an agent fleet to find and fix small bugs in a large repo **autonomously**:
a deterministic `conductor` claims tasks from a queue, delegates each step to an
isolated agent subprocess, records everything in an append-only history DB, and
leaves PR-ready branches. The human reviews and submits upstream.

Reference implementation: `playground/cluster/` over the LibreOffice core work
clone (`lo-writer`) — see `references/libreoffice-writer-cluster-notes.md`.

## Pipeline (per task)

```
claim → upstream check (searcher: bugzilla+gerrit) → investigate (inspector A:
root cause + file:line proposal) → implement+verify+commit (inspector B) →
record (history DB + tracker report) → pr_ready branch on origin
```

- **Isolation**: each agent step runs as a subprocess with a hard timeout
  (crash/hang containment, no shared state). Timeout → task marked blocked, not
  a crash.
- **History DB is append-only** (tasks/actions/commits/reverts). Queues pick
  `pending` only — a blocked task needs a manual `pending` requeue to retry.
- **Verification levels recorded per commit**: V0 unverified (needs upstream CI,
  must say why), V1 static/format, V2 script/unit test, V3 compiled. Full big-repo
  builds are hours — the cluster does NOT run them; upstream CI is the final gate.

## The #1 lesson: a fix engineer needs FILE-WRITE tools, not just git tools

The classic structural failure: inspector B has `git_create_branch`, `git_commit`,
`git_push` but **no way to edit a source file** (repo tools are read-only). Every
implementation run then follows a doomed script: create branch → try to modify
code → (no tool) → burn the whole step budget → nothing committed.

Provide at minimum:
- `git_write_file(rel_path, content)` — full overwrite, **path-escape guard**
  (resolve + verify the target stays under the work clone; reject `../..`).
- `git_patch_file(rel_path, old_string, new_string)` — surgical single replace,
  refuse when old_string appears 0× or >1× ("include more context").
- Scoped git tools: branch name regex (`writer/<bug-id>-<slug>`), commit only on
  `writer/*`, push only to origin, `git add -A` before commit.

Verify the agent's tool list matches what the conductor's prompt names — a
prompt referencing tools the agent doesn't have produces silent wasted runs.

## Conductor success detection

Detect a finished fix by **committed branches**, not the current branch:

```python
git branch --list "writer/*" --format=%(refname:short)
# then pick a branch with: git log --oneline master..<branch>  (non-empty)
```

Impl instructions tell the agent to `git_switch_master` after pushing, so
"current branch starts with writer/" is a WRONG success signal — a successful
fix would be reported blocked.

## Verify pushes — self-reports are not facts

- The conductor's "pushed" print text is not evidence. After the implement step,
  verify with `git ls-remote origin <branch>` (or the GitHub API) before marking
  `pr_ready`.
- **Empty-origin bootstrap trap**: pushing ANY branch to an empty repo requires
  uploading the entire base tree (single-commit shallow clones are the whole
  repo). An empty `origin` makes every push huge; seed `master` first, then
  writer branches are tiny. Check `gh api repos/<owner>/<repo>` size/branches
  when pushes keep "succeeding" without landing.
- **Test transport with a tiny push first** (e.g. empty-tree commit) when big
  pushes fail — distinguishes transport failure from repo/object problems.
- **Exit codes in pipelines**: `$?` after `cmd | tail` is `tail`'s exit, not
  `cmd`'s — use `${PIPESTATUS[0]}` or redirect to a file.

## Memory-store integration pitfalls

- **FTS5 chokes on `#`** (bug IDs!): `where fts match 'tdf#90152'` raises
  `fts5: syntax error near "#"` and breaks the agent's memory_search mid-task.
  Sanitize: keep word chars only, quote each token as a phrase, AND-join
  (`"tdf" AND "90152"`), and catch `OperationalError` → fall back to vector-only.
- Agents hitting a broken tool will often end their turn with the tool error and
  no work done — a single tool bug can stall the whole pipeline. Fix the tool,
  then requeue the task.

## Step budgets

- 900 s per step was too tight for a multi-tool investigation (deepseek-v4-flash
  + rg/ctags/read + memory search); 1800 s worked. Budget the INVESTIGATE step
  generously — it is the heavy one.
- Blocked-by-timeout is not fatal: log the reason, requeue `pending`, rerun.

## References

- `references/libreoffice-writer-cluster-notes.md` — the LibreOffice cluster's
  actual layout, task queue, standards (verification levels, commit format),
  and the debugging timeline that produced the lessons above.
