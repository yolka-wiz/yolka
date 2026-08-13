# Cluster orchestration — full pipeline and bug log (verified 2026-08-10)

Reference: `/home/agent/workspace/playground/cluster/` — conductor.py,
history_db.py, tracker.py, standards.md, status.md. Driven on cron every 30 min
via `lo-cluster-tick.sh` (no_agent mode: stdout is the delivery).

## Pipeline (one iteration = one task)

```
claim → upstream_check (searcher) → investigate (inspector_a) →
implement+verify+commit+push (inspector_b) → record → report (tracker.py)
```

- Upstream check answers GREEN vs ALREADY_UPSTREAM (Bugzilla status + Gerrit
  open changes referencing the bug); ALREADY_UPSTREAM → task `skipped`.
- Investigation failure / timeout → task `blocked` with the error note.
- Implementation ends → conductor looks for a committed `writer/*` branch.
- Every significant step is logged to the history DB (agent, action, target,
  status). Tracker renders `cluster/status.md` deterministically.

## Bugs found in the first two runs (each cost one full iteration)

1. **Step timeout too tight.** `MAX_STEP_SECONDS=900` → inspector_a TIMEOUT
   on the first run; task#2 also got `stuck-investigating`. Fix: 1800.
2. **FTS5 `#` syntax error.** `memory_search("tdf#90152 …")` →
   `fts5: syntax error near "#"`. Hit by BOTH agents mid-pipeline; the
   implement run ended right after the tool error, leaving an empty branch.
   Fix in `memory_store._fts5_safe_query()`: `re.findall(r"\w+", q)` →
   `" AND ".join(f'"{t}"' ...)` + try/except `OperationalError` → `[]`.
3. **Conductor false BLOCKED.** Success check used `git branch --show-current`,
   but the implement instructions tell the agent to `git_switch_master` after
   pushing — so success always looked like "no branch". Fix: list
   `writer/*` branches, accept one with commits beyond master.
4. **Fix engineer had no file-write tool.** inspector_b had git branch/commit/
   push but nothing that edits a file — the implementation step was
   structurally impossible. Fix: add `git_write_file` + `git_patch_file`
   (scoped to the work clone, path-escape guard, ambiguity check on
   old_string) and include them in the agent's tool list.

## Requeue workflow (blocked → pending)

The queue only picks `status='pending'` — a blocked task never retries itself.
Manual reset (documented in the history DB each time):

```python
from cluster.history_db import get_history
h = get_history()
h.set_task_status(1, 'pending', notes='requeued: <why>')
h.log('conductor', 'reset', 'task#1', 'blocked -> pending: <what changed>', 'ok')
```

Then run `python cluster/conductor.py` (or let the cron tick).

## Sanity checks before trusting a "done"

- `git -C lo-writer log --oneline -3 writer/<branch>` — real commit beyond master?
- `git -C lo-writer ls-remote origin 'writer/*'` — actually pushed?
- `git -C lo-writer diff --stat master..<branch>` — non-empty diff?
- History DB: task status, actions log, recorded commit SHA.

An empty branch (exists, no diff, no push) is a FAILED run, not progress.
