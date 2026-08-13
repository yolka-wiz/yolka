---
name: autonomous-code-fix-cluster
description: "Run agent fix clusters: conductor pipeline, tools, pitfalls."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agents, cluster, conductor, git, fts5, sqlite-vec, automation, cron]
    related_skills: [agno-agent-playground, mcp-server-verification, git-essentials]
---

# Autonomous Code-Fix Cluster

Operate an autonomous agent cluster that picks small tasks (bugs/optimizations)
from a queue, investigates, implements fixes in a **writable clone**, commits on
a `writer/*`-style branch, pushes, and records everything in an append-only
history DB — driven by a deterministic `conductor.py` on cron (no_agent mode).

Reference implementation: `/home/agent/workspace/playground/cluster/`
(conductor.py, history_db.py, tracker.py, standards.md) operating on
`lo-writer` (writable) vs `libreoffice-core` (read-only index clone).

## Architecture invariants

- **Two clones**: read-only index/source-of-truth + writable work clone. Agents
  never touch the read-only one; edits only in the work clone.
- **Subprocess isolation**: each agent step runs as its own subprocess with a
  hard step timeout; a hang/crash is contained and logged, never propagated.
- **Append-only history DB**: tasks (queue+status), actions (audit log),
  commits, reverts. Nothing deleted; reverts recorded.
- **Deterministic tracker**: renders status.md from the DB without an LLM.
- **Lifecycle**: `pending → investigating → implementing → verifying → committed → pr_ready`, with `blocked` / `skipped` / `reverted` exits. Cron picks only `pending`, smallest-size-first — **a blocked task never retries itself; it needs a manual requeue**.

## The failure modes that cost real runs (all verified 2026-08-10)

1. **Fix agents need BOTH git tools AND file-write tools.** The #1 structural
   trap: agent has `git_create_branch`/`git_commit`/`git_push` but no way to
   edit a file → it burns the entire step budget and produces an empty branch
   (or none). Before first run, wire scoped `git_write_file` + `git_patch_file`
   (full-file overwrite + single-replace with ambiguity check, both with a
   path-escape guard resolving under the work clone).

2. **FTS5 breaks on `#` and other specials.** Memory-search queries containing
   bug IDs (`tdf#90152`) raise `fts5: syntax error near "#"`, which breaks
   agent tool calls mid-pipeline. Sanitize every FTS5 match input: tokenize
   with `\w+`, phrase-quote each token, AND-join; wrap the query in
   try/except `OperationalError` → fall back to vector-only.

3. **Success detection must not use the current branch.** The implement
   instructions tell the fix agent to `git checkout master` after pushing, so
   `branch --show-current` always reads `master` and a successful fix looks
   BLOCKED. Detect via `git branch --list 'writer/*'` and pick a branch with
   a real commit beyond master (`git log --oneline master..<branch>`).

4. **Step timeouts**: 900 s was too tight for a multi-tool investigation
   (repeated timeouts / stuck-investigating); 1800 s per step worked.

5. **agno `@tool` returns a Function object, not a callable** — for direct
   Python invocation use `f.function` (or `.entrypoint`), not `f(...)`.

6. **Never run `.py` scripts via `env python` from subprocesses** — system
   python lacks the venv deps and fails silently (ImportError swallowed by
   `capture_output=True`). Always `[venv/bin/python, script.py]`.

## Tool wiring checklist for the fix engineer

- git: status, create_branch (`writer/<bug-id>-<slug>` regex-validated), diff,
  commit (subject must start `tdf#<id>`/`opt-`), push (only writer/*), switch
  master, **write_file, patch_file** (scoped, escape-guarded)
- read: rg, ctags, safe read_file (read-only clone)
- memory: add/search/fact/stats (with FTS5 sanitization)
- publish: results-repo upload (commit + push) for completed findings

## Verification levels (record on every commit)

V0 unverified (upstream CI only) · V1 static/format (xmllint, script) ·
V2 script/unit test ran · V3 compiled (module build). Full LO builds are hours;
the cluster never runs them — Gerrit CI stays the final gate, stated in every
pr_ready summary.

## Details & references

- Full conductor pipeline, the four bugs fixed, and the requeue workflow:
  `references/cluster-orchestration.md`
- Embedding model selection under 2 CPU / <2 GB RAM (measured bge-small vs
  Qwen3-Embedding-0.6B, incl. the sentence-transformers 32k-padding trap):
  `references/embedding-model-benchmark.md`
- Fleet build (agents, sql-vec memory, MCP, FastAPI) lives in the
  `agno-agent-playground` skill.

## Pitfalls recap (fast scan)

- fix agent has no file-write tool → empty branch every run; add write/patch tools
- FTS5: `#` in query → sanitize (`\w+` tokens, phrase-quoted, AND) + fallback
- conductor: list `writer/*` branches with commits, never `--show-current`
- blocked tasks don't requeue themselves — manual reset to `pending`
- agno Function objects: `.function` to call directly
- subprocess `.py` → venv python, not `env python`
- benchmark only until the resource verdict is clear — user prefers stopping
  over rabbit-holing on quality evals when RAM/speed already decide
