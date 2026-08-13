# Cluster design + fixes (reference, 2026-08)

## Pipeline (conductor.py run_iteration)

1. `next_task()` → claim → searcher **upstream check**
   (bugzilla/gerrit; GREEN vs ALREADY_UPSTREAM → skip)
2. inspector_a **investigate** (read-only index clone; deliver root cause,
   file:line fix proposal, verification level V0–V3, risks)
3. inspector_b **implement** (writable work clone; branch
   `writer/<bug-id>-<slug>`; apply change; verify; commit; push; switch master)
4. record commit + status `pr_ready`; tracker.py renders status.md
   (publishes to results repo)

Isolation: agents run as subprocesses with a hard step timeout; timeout/error
strings flow into the pipeline as blocked states — never raises.

## History DB shape

- tasks(id, title, bug_id, module, kind, size, status, branch, commit_sha,
  assigned_agent, notes, timestamps)
- actions(ts, agent, action_type, target, detail, status) — append-only audit
- commits / reverts / settings

Queue: `select * from tasks where status='pending' order by
case size when 'S' then 0 when 'M' then 1 end, id asc limit 1` — blocked
tasks need manual requeue (set status='pending' + note).

## Fixes applied to the reference cluster (all verified)

| Symptom | Root cause | Fix |
|---|---|---|
| inspector_a TIMEOUT after 900 s | step budget too tight for multi-tool investigation | MAX_STEP_SECONDS 900 → 1800 |
| `fts5: syntax error near "#"` in memory_search | FTS5 special chars in bug-id queries | `_fts5_safe_query()`: tokenize `\w+`, phrase-quote, AND-join; catch OperationalError → vector-only fallback |
| "no branch created" false-block after a real run | conductor checked `branch --show-current`; agents switch back to master | list `writer/*`, pick branch with commits beyond master |
| inspector_b "did nothing" for 30 min | git tools but NO file-write tool | add `git_write_file` + `git_patch_file` (scoped to work clone, escape-guarded) |
| push "reported ok" but never landed | empty origin; no verification | hard 120 s timeout + `ls-remote` verification in git_push |

## Verification patterns

- Requeue: `h.set_task_status(id,'pending', notes=...)` + action log entry.
- Before trusting a fix: `git log master..<branch>`, `git diff --stat
  master..<branch>`, `git ls-remote origin refs/heads/<branch>`.
