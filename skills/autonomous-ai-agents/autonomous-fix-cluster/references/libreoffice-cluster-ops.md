# LibreOffice Writer autonomous cluster — ops notes (2026-08-10)

Real debugging session. The cluster is at `/home/agent/workspace/playground/cluster/`
(conductor.py, history_db.py, tracker.py, standards.md, status.md).

## Architecture facts

- **conductor.py** drives one task per iteration, safe on cron (`*/30` via
  `lo-cluster-tick.sh`, no_agent mode). Pipeline:
  `claim → searcher upstream_check → inspector_a investigate → inspector_b
  implement → record → tracker report`. Steps run as isolated subprocesses
  (`subprocess.run([PY, "-c", code], timeout=MAX_STEP_SECONDS)`), so a hang is
  contained and becomes an error string, never a crash.
- **history DB**: `playground/data/cluster_history.db` — tables tasks/actions/
  commits/reverts/settings, append-only. `next_task()` picks pending, size S
  first, oldest first. Blocked tasks are NOT re-picked — manual requeue
  (`set_task_status(id, 'pending', notes=...)`) is required after a block.
- **Clones**: `libreoffice-core` = read-only index clone (ctags/rg/memory);
  `lo-writer` = writable work clone; origin = `yolka-wiz/libreoffice-work`,
  upstream = `LibreOffice/core`.
- **Task queue** (from Bugzilla easyHack research): tdf#87605 (technical
  dictionary, extras/), tdf#119931 (.ui a11y warnings), tdf#82579 (premac.h
  removal), tdf#90152 (printed comments formatting — first DONE), tdf#35055
  (paragraph shadow), tdf#35515 (autocorrect email), tdf#35304 (chart 3D).

## Bugs found and fixed (chronological)

1. **Investigate step timed out at 900 s.** `MAX_STEP_SECONDS` was too tight
   for multi-tool reads + model latency → raised to 1800 s. Task#2 showed the
   same `stuck-investigating` symptom earlier — pattern, not one-off.
2. **`memory_search` crashed with FTS5 syntax error.** Query `tdf#90152 ...`
   → `fts5: syntax error near "#"`. Both inspector agents hit it; it derailed
   the implement run. Fix in `memory_store.py`:
   ```python
   def _fts5_safe_query(query: str) -> str:
       tokens = re.findall(r"\w+", query, flags=re.UNICODE)
       return " AND ".join(f'"{t}"' for t in tokens) if tokens else '""'
   ```
   plus `try/except sqlite3.OperationalError: return []` (fall back to
   vector-only).
3. **Conductor reported "no branch created" for a successful run.** Success
   check was `git branch --show-current`, but the impl prompt tells inspector_b
   to `git_switch_master` after pushing → current branch is master even on
   success. Fix: list `writer/*` branches and require a commit beyond master:
   `git log --oneline master..<branch>` non-empty. Also the "pushed" print was
   just text — no remote verification. (Bootstrap push verification was the
   follow-up; see #5.)
4. **Fix engineer had no file-write tool.** inspector_b had git branch/commit/
   push tools (from `tools/git_tools.py`) but repo_tools are read-only →
   structurally unable to edit `doc.cxx`. It burned two full budgets producing
   an empty branch. Fix: added `git_write_file(rel_path, content)` and
   `git_patch_file(rel_path, old_string, new_string)` to git_tools.py —
   scoped to lo-writer with a path-escape guard, single-replace with ambiguity
   check (`text.count(old)` == 1). All agents rebuilt automatically since
   `git_tools()` is wired into inspector_b.
5. **Empty-origin bootstrap trap.** `yolka-wiz/libreoffice-work` was created
   but EMPTY (0 KB, no branches — confirmed via `gh api repos/... --jq
   '.size'`). Every push hung uploading the 588 MB snapshot. Fix: switched
   origin to SSH (`git@github.com:yolka-wiz/libreoffice-work.git`), pushed
   master once in background, then writer/* branches are tiny.
6. **Pipeline exit-code trap.** `git push ... | tail -4; echo $?` reports
   tail's exit, not git's — first "push exit=0" was meaningless. Use
   `PIPESTATUS[0]` or capture to a file with `REAL_EXIT=$?`.

## Result (verified end-to-end)

- tdf#90152 fix landed: commit `76898c2b` on
  `writer/tdf-90152-postit-print-locale`, +39/−11 in
  `sw/source/core/doc/doc.cxx` — locale-aware list separator
  (`SvtSysLocale::getListSep`) + bold labels; NOT the naive English-only fix
  the maintainer warned about.
- History DB: task#1 = `pr_ready`, commit recorded; results repo got the agent
  result + cluster status update.

## Network evidence (flaky link to github.com)

- `git fetch --unshallow` → `fatal: early EOF / invalid index-pack` (3 retries).
- `git fetch origin master --shallow-since=2025-08-01` → also `early EOF`
  (pack still too big).
- `git fetch origin master --depth=200` → OK, 192 commits (≈8 commits behind
  tip; snapshot was already nearly current).
- HTTPS push → hung at `POST git-receive-pack (chunked)`; SSH push worked.
- `gh api` / REST worked reliably throughout (used to inspect repo state).

## Verification levels used by this cluster (standards.md §5)

V0 unverified/upstream-CI-only · V1 static (xmllint/regex) · V2 script/unit
test · V3 module build. Full LO build is hours — never run locally; Gerrit CI
is the final gate. Commit format: `tdf#<id> <summary>` subject + what/why/
verification body.
