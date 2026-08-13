---
name: autonomous-fix-cluster
description: "Autonomous agent fix clusters: conductor, tools, verify."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agents, orchestration, conductor, bug-fixing, git, verification, libreoffice]
    related_skills: [agno-agent-playground, bug-tracker-triage, git-essentials, open-source-triage]
---

# Autonomous Fix Cluster

Run a fleet of agents that autonomously fix real bugs in an OSS codebase,
end-to-end: claim task → upstream check → investigate → implement → verify →
commit → push → report. The conductor drives one task per iteration (cron-safe),
agents run as isolated subprocesses, and a deterministic history DB keeps an
append-only audit trail.

Reference implementation: `/home/agent/workspace/playground/cluster/`
(LibreOffice Writer cluster, 2026-08-10). Detailed debugging notes:
`references/libreoffice-cluster-ops.md`.

## 1. Conductor pipeline (one iteration)

```
claim → searcher upstream_check (Bugzilla/Gerrit: GREEN vs ALREADY_UPSTREAM)
      → inspector_a investigate (root cause + fix proposal, file:line evidence)
      → inspector_b implement (branch → edit → verify → commit → push → switch master)
      → record (history DB: task status, commit sha, branch)
      → report (deterministic tracker renders status.md; publishes to results repo)
```

- Queue picks smallest-size pending tasks first (`order by size, id`).
- Upstream check first: if ALREADY_UPSTREAM → mark `skipped`, never duplicate.
- Every step logs to the history DB (agent, action, target, status) — append-only.

## 2. The three structural traps (each burned a full pipeline run)

1. **Agent-tool completeness check FIRST.** Enumerate each agent's tools
   (`sorted(t.name for t in build_agents()[x].tools)`) and cross-check against
   every tool name its prompts reference. Our fix engineer had git
   branch/commit/push tools but NO file-write tool → structurally unable to
   edit code; it burned two full step budgets producing nothing. Add the
   missing tools (`git_write_file` + `git_patch_file` scoped to the work repo,
   with a path-escape guard) BEFORE rerunning.
2. **Success detection must verify the artifact, not the current state.**
   A conductor checking `git branch --show-current` reports "no branch" for a
   SUCCESSFUL run (impl instructions tell the engineer to switch back to
   master after pushing). Detect committed work branches instead:
   `git branch --list writer/*` + `git log --oneline master..<branch>` non-empty.
   For pushes, verify `git ls-remote origin <branch>` — never trust an agent's
   "pushed" claim (the conductor's print text is not evidence).
3. **Isolated subprocess steps need a realistic budget.** 900 s was too tight
   for a multi-tool investigation on a slow model; 1800 s/step works. Timeout
   must exceed the worst-case legitimate step. Timeouts/errors become error
   strings the pipeline handles — never exceptions.

## 3. Agent memory tool hygiene (FTS5)

If agents search shared memory via SQLite FTS5, sanitize the query BEFORE the
`match ?` — raw queries with `#`, `"`, `*`, `-`, `(` raise
`fts5: syntax error near "#"` (real case: `memory_search("tdf#90152 ...")`
broke an agent mid-pipeline). Tokenize `re.findall(r"\w+", q)`, phrase-quote
each token (`"tok1" AND "tok2"`), and catch `sqlite3.OperationalError` → fall
back to vector-only results. Never let a search tool crash an agent turn.

## 4. Verification levels (record on every commit)

| Level | Meaning | When acceptable |
|---|---|---|
| V0 | unverified — needs upstream CI | only when no local check possible; MUST state in commit body |
| V1 | static/format validated (xmllint, script, regex) | data/XML/script fixes |
| V2 | script/unit tested (agent wrote and ran a test) | logic with testable unit |
| V3 | compiled (module-scope build) | when a build is available |

Full OSS builds (e.g. LibreOffice) take hours — the cluster does NOT run them;
upstream CI (Gerrit) is the final gate. Never fake verification.

## 5. GitHub on flaky links (fetch + push)

- `git fetch --unshallow` and big HTTPS transfers die with `early EOF` /
  `invalid index-pack`; pushes hang at `POST git-receive-pack (chunked)`.
- Ladder down instead of retrying the same size: `--shallow-since=<date>`
  (1 year OK) → `--depth=<N>` (200 worked; gave 192 commits + blame window).
- Harden http: `postBuffer 524288000`, `lowSpeedLimit 0`, `lowSpeedTime 600`,
  `http.version HTTP/1.1`, `fetch.negotiationAlgorithm noop`.
- Prefer SSH remotes for push (`git@github.com:<owner>/<repo>.git`) — verified
  reliable where HTTPS chunked hangs. Test: `ssh -T git@github.com`.
- Empty-origin bootstrap trap: a work repo created but never seeded makes the
  first push upload the whole snapshot (LO = 588 MB pack) → repeated hangs.
  Bootstrap once (`git push -u origin master` over SSH, background), then
  writer/* branch pushes are tiny.
- `$?` after a pipeline captures the LAST command (`tail`), not git — capture
  to a file and check `PIPESTATUS` or run without the pipe.

## 6. Verification checklist

1. `build_agents()` → every tool name referenced by prompts exists on the agent.
2. Full pipeline on ONE size-S task: claim → GREEN → investigate → implement →
   commit → push → history DB `pr_ready` with real sha.
3. `git ls-remote origin <branch>` shows the branch (push actually landed).
4. Memory search with a bug-id query (`tdf#12345 ...`) returns results, no error.
5. Tracker status.md reflects the new commit; results repo updated.
