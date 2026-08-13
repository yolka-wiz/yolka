---
name: autonomous-bug-fix-cluster
description: "Operate and repair autonomous bug-fix agent clusters."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agno, agents, cluster, conductor, history-db, sqlite-vec, git, github, push]
    related_skills: [agno-agent-playground, bug-tracker-triage, github-repo-management]
---

# Autonomous Bug-Fix Cluster Operations

Operate, repair, and extend an autonomous multi-agent bug-fix cluster: a
conductor drives a queue of bugs/opt-tasks through investigate → implement →
commit → push, with an append-only history DB and a tracker report. Reference
implementation: `/home/agent/workspace/playground/cluster/` (LibreOffice
core), cron tick every 30 min.

## Architecture

- conductor.py — one iteration per run (safe on cron): claim → searcher
  upstream check (GREEN/ALREADY_UPSTREAM) → inspector_a investigate →
  inspector_b implement+commit+push → record → tracker. Agents run as isolated
  subprocesses; timeouts become error strings the pipeline handles.
- history_db.py — append-only SQLite: tasks (queue+status), actions (audit),
  commits, reverts. Queue picks only status='pending' (S size first).
- standards.md — lifecycle, verification levels V0–V3, commit format.
- Two clones: read-only index clone + writable work clone (origin = own
  GitHub fork of upstream).

## Gotchas (each cost a real debug cycle)

1. **Step timeouts are budget, not logic.** 900 s/step blocked a multi-tool
   investigation; raise to 1800 s. Blocked tasks never re-queue — the queue
   only picks `pending`; requeue manually after fixing the cause.
2. **The fix engineer must be able to edit files.** Git tools alone
   (branch/commit/push) with no write/patch tool = structurally broken: it
   creates a branch, cannot change code, burns the budget, commits nothing.
   Verify the tool list includes write/patch tools scoped to the work clone
   (path-escape guard: resolve + prefix check).
3. **Success detection must not trust the current branch.** Agents switch back
   to master after pushing, so `git branch --show-current` reports failure on
   every success. Detect by listing `writer/*` and picking a branch with
   commits beyond master.
4. **Push must be verified, not assumed.** Give the push tool a hard timeout
   (120 s) + `git ls-remote origin refs/heads/<branch>` verification. A
   hanging network must fail fast (else it eats the whole agent budget); a
   reported "pushed" that never landed derails the pipeline silently. The
   conductor's own "pushed" print is NOT evidence.
5. **FTS5 rejects special chars.** memory_search with bug IDs (`tdf#90152`)
   throws `fts5: syntax error near "#"` and breaks the agent's flow. Sanitize
   queries (word chars only, phrase-quoted, AND-joined) and fall back to
   vector-only on OperationalError.
6. **agno `@tool` is not callable.** It returns a Function wrapper;
   orchestrators must call a plain `*_impl()` function (or `.function`).
7. **Self-reports are not facts.** An "empty origin" made every push fail
   while the pipeline reported success. Verify external side effects
   (ls-remote / gh api) independently before declaring done.

## References

- references/cluster-design.md — full design + fixes made in the reference
  cluster (2026-08).
- references/remote-git-bootstrap.md — empty-origin bootstrap via server-side
  fork, local pack reproduction of remote push failures, GitHub throttle
  diagnosis, bounded fetches when `--unshallow` fails.
- references/embedding-benchmarks.md — measured bge / MiniLM / Qwen3 numbers
  and the sentence-transformers 32k-padding trap.
