---
name: lo-autonomous-bug-cluster
description: "Operate the LibreOffice autonomous bug-fix cluster."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [libreoffice, cluster, conductor, autonomous, git, bug-fixing, agents]
    related_skills: [agno-agent-playground, libreoffice-git-github-push]
---

# LibreOffice Autonomous Bug-Fix Cluster

An autonomous fleet that claims small LibreOffice `sw/` bugs, investigates,
fixes, commits, pushes, and reports — driven by a conductor on a cron tick.
Lives in `/home/agent/workspace/playground/cluster/`.

## Components

| Piece | File | Role |
|---|---|---|
| Conductor | `cluster/conductor.py` | one iteration: claim → upstream check → investigate → implement → commit → record → report |
| History DB | `playground/data/cluster_history.db` | append-only audit: tasks, actions, commits, reverts |
| Standard | `cluster/standards.md` | task lifecycle, verification levels (V0–V3), commit format |
| Tracker | `cluster/tracker.py` | renders `cluster/status.md` (deterministic, no LLM) |
| Cron | `lo-writer-cluster-tick` | every 30 min, `no_agent`, runs `lo-cluster-tick.sh` → conductor |

Clones: read-only index `libreoffice-core`, writable work `lo-writer`
(origin = `yolka-wiz/libreoffice-work`, a **public fork** of LibreOffice/core).
Agents: searcher (upstream check), inspector_a (investigate), inspector_b (fix
engineer, git tools), indexer (memory hygiene).

## Operating runbook

- **Run one iteration manually:** `cd /home/agent/workspace/playground && .venv/bin/python cluster/conductor.py`
- **Status:** `cluster/status.md` or `history_db.py` (stats/tasks/actions)
- **Unblock a blocked task:** `h.set_task_status(<id>, 'pending', notes='...')` in a `history_db` shell. `next_task()` only picks `pending`, so a blocked task never auto-retries.
- **Inspect the audit trail:** `h.recent_actions(30)` — every step is logged.
- **Verify before believing:** the conductor's "DONE — branch pushed" is its own print; confirm with `git -C lo-writer ls-remote origin refs/heads/writer/*` or the GitHub API.

## Hard-won pitfalls (each cost a debug cycle — fix before re-triggering)

1. **Step timeout too tight.** `MAX_STEP_SECONDS = 900` blew up inspector_a's
   investigation (multi-tool reads + model latency). Raised to `1800`.
2. **FTS5 crashes on `#`.** `memory_search("tdf#90152 …")` → `fts5: syntax error
   near "#"`. Fixed in `memory_store._fts5_safe_query()`: tokenize word chars and
   quote each as a phrase, AND-joined; catch `OperationalError` → vector-only.
3. **Fix engineer had NO file-write tool.** `repo_tools` is read-only; `git_tools`
   only did branch/commit/push. inspector_b could create a branch but never edit a
   file (burned the whole budget). Added `git_write_file` + `git_patch_file`
   (both scoped to `lo-writer` with a path-escape guard).
4. **Conductor detected success via `git branch --show-current`** — but impl
   instructions tell the agent to switch back to `master` after pushing, so a
   *successful* fix looked "no branch created". Fixed: list `writer/*` branches
   and pick one with a real commit beyond `master`.
5. **Push timeout too short for the slow fork.** A 7-object push to the 6.9 GB
   fork takes GitHub *minutes* of server-side `receive-pack`. `git_push` was
   120 s (always failed) → raised to `300 s` + `ls-remote` verification so a
   hanging network fails fast but a slow server succeeds. See
   `libreoffice-git-github-push` skill.
6. **Empty-origin bootstrap.** origin was an empty repo → any push uploaded the
   whole 350 MB snapshot and died. Solved by **server-side fork** of
   LibreOffice/core (GitHub copies refs; pushes become tiny deltas).
7. **`env python` subprocess trap.** Scripts run via shebang use *system* python
   (no dotenv/sqlite_vec) → silent ImportError. Always invoke
   `.venv/bin/python <script>`.

## Task lifecycle

`pending → investigating → implementing → verifying → committed → pr_ready`,
with `blocked → requeue or skip`. S tasks first. Never fake verification — V0
(unverified, needs upstream CI) is allowed only with a stated reason. Commit
message: `tdf#<id> <summary>` + what/why/verification body. Full LO build is
hours — the cluster does NOT run it; upstream Gerrit CI is the final gate.
