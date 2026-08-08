# al-bdf wave dispatch — worked recipe (M10, 2026-08-06)

Project-specific application of the parallel-worktree pattern. Repo:
`/home/agent/workspace/al-bdf-engine`, tracking DB `db/albdf.db` (gitignored).

## Pre-dispatch sequence (all orchestrator-side, verified working)

1. **Sync the repo** — this repo has been history-rewritten once (filter-repo
   personal-info scrub, all commits re-authored to `Yolka <yolka@albdf.local>`).
   On `git fetch`, "forced update" on main is EXPECTED after any scrub; before
   hard-resetting, confirm no local-only commits (`git log origin/main..HEAD`)
   and diff your old tip against the rewritten commit with the same subject
   (`git diff <old> <rewritten>` empty = pure renumber, safe to reset).
2. **Baseline gate — verify FRESH, not just green.** `QT_QPA_PLATFORM=offscreen
   ctest --test-dir src/build --output-on-failure` must pass BEFORE dispatch —
   but first confirm the binary is not stale: `stat -c %y src/build/bin/albdf`
   vs `git log -1 --format=%ci HEAD`. If the binary predates HEAD (or the
   last feature merge), rebuild from clean or children will hit a phantom
   baseline. REAL FAILURE 2026-08-06: M9 wave-1 merge (`4402b1c`) added
   QFlags values past bit 31 (`MovePage = 0x100000000`, `DeletePage =
   0x200000000`) so main never compiled on Qt 6.8/6.10; the pre-merge binary
   gave a false 11/11 and ALL three children hit the compile break. Fix:
   replace `Q_DECLARE_FLAGS` with a 64-bit `Options` class (`4bb644f`) —
   see qt-cmake-vcpkg-build skill references for the full case.
3. **Reconcile DB** — docs (PLAN.md/RELEASES.md) may cite closed tasks that
   have no rows: re-add them with `python3 scripts/db.py task-add --component
   <name> --title "..." --priority N --assignee <role>` then
   `task-done <id> --ref <sha>` using the refs already in the docs. Then add
   the next wave as open tasks.
4. **Worktrees** — one per agent role, branch per repo convention
   `m<milestone>/<slug>`:
   ```bash
   git worktree add -b m10/rtl-crossline-search /home/agent/workspace/wt-rtl-crossline origin/main
   # DB is gitignored → copy it in or children see an empty tracking DB:
   cp db/albdf.db /home/agent/workspace/wt-<slug>/db/
   ```
5. **Execution plan per worktree** — write `plans/m10-<slug>-execution.md`
   inside the worktree, commit as `docs(plan): ...` on the branch so the
   branch history carries the plan.
6. **Dispatch** — one leaf per worktree via delegate_task batch (max 3
   concurrent for this profile). Context must include: worktree path +
   "never the main checkout", the repo's binding AGENTS.md path, EXACT build
   commands, TDD RED→GREEN order, Conventional Commits, report-back contract.

## Environment facts that differ from repo docs (verify before writing contexts)

- **vcpkg is NOT at `/workspace/vcpkg`** (src/AGENT.md lies on this machine).
  Real path: `/home/agent/vcpkg-cache/vcpkg`; export
  `VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg` and use
  `$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake`. vcpkg binary cache at
  `~/.cache/vcpkg` makes worktree builds reuse deps.
- Build dirs: `src/build` (Release, Ninja), `src/build-asan` (Debug+ASAN);
  both gitignored, per-worktree.
- CLI binary: `src/build/bin/albdf`; commands self-register via static
  instances (`static PDFToolX s_xApplication;`) — so `binary --help`'s
  command list is the truth oracle for whether a command is wired.

## Recon oracle for "is this task actually missing?"

For a task claiming "wire upstream X": check the command list
(`albdf 2>&1 | grep X`), the static registration file exists, and the file is
in `src/PdfTool/CMakeLists.txt`. All three true → wiring exists; the child's
scope is verification + tests + evidence closure, not implementation.
(Redact: upstream `pdftoolredact.cpp` + `pdf::PDFRedact` were already wired;
the DB task wording was stale.)

## Shared-blocker recovery (all children hit the same wall)

When every parallel child reports the SAME pre-existing compile failure:

1. **Read all child summaries first** — they may also have caught plan errors
   (redact reality: no `--page` flag; regions come only from Redact
   annotations embedded in the PDF — multipage.pdf has none, so a plain
   redact is a no-op; need a `/Subtype /Redact` annotated fixture).
2. **Fix on main, rebuild from clean, get the REAL green** (fresh ctest).
3. **Propagate into worktrees by file copy + per-branch commit** — NOT
   cherry-pick, which balks when children left uncommitted fix variants:
   ```bash
   for wt in wt-rtl-crossline wt-core-redaction wt-infra-fuzz; do
     cp al-bdf-engine/src/PdfTool/<fixed-file> $wt/src/PdfTool/<fixed-file>
     git -C $wt add ... && git -C $wt commit -m "fix(cli): ..." --no-verify
   done
   ```
4. **Re-dispatch fresh children** crediting the cap-hit run's investigation
   ("the blocker is fixed on this branch: <sha>; a previous agent found X —
   trust it, do not re-derive"). If a child already committed a verified RED
   test before the cap (real output shows it failing for the right reason),
   the orchestrator commits it itself rather than re-dispatching for that.
5. **Record the trap** — PROBLEMS.md entry + DB task closed with the fix sha
   (e.g. #31 → `4bb644f`), so the version-drift trap is institutional memory.

## Core-bug-during-verification: child stops, orchestrator implements core

Distinct from the shared-blocker case: a single child, mid-verification,
discovers a REAL bug in core/vendored code OUTSIDE its declared scope (here:
`PDFDocumentBuilder::createTrailerDictionary` stamped
`QDateTime::currentDateTime()` into CreationDate/ModDate → redact/unite output
not byte-deterministic, violating AGENTS.md §2.1). The child did the RIGHT
thing per the repo contract: stopped and asked the orchestrator instead of
improvising a change to `Pdf4QtLibCore` (its plan restricted edits to
`src/PdfTool/`). Orchestrator response that worked:

1. **Authorize + implement the core fix yourself** — core-library design
   judgment (deterministic-date policy: honor `SOURCE_DATE_EPOCH` else fixed
   epoch, matching scripts/package.sh) is orchestrator work, not leaf work.
   Fix the root at the factory (`PDFObjectFactory::operator<<(WrapCurrentDateTime)`)
   so all ~13 date sites (trailer Info, signatures, annotations) get fixed at
   once.
2. **Prove the fix yourself with the sleep-separated determinism test**
   (`redact in a.pdf && sleep 3 && redact in b.pdf && sha256sum a.pdf b.pdf` →
   identical) — do NOT take your own patch on faith; this is the same
   verify-don't-believe rule applied to yourself.
3. **Commit core fix + the child's uncommitted-but-verified artifacts**
   (fixture + generator) yourself, THEN dispatch a **finisher** child for the
   mechanical remainder (write the pixel-based test, wire CMake target, full
   ctest). Context must say explicitly: "implementation, fixture, and
   determinism fix are ALL already committed — this is test-wiring only."
4. The finisher may still hit the tool cap; harvest it the same way (read the
   summary, verify its claims, commit any verified artifacts, re-dispatch).

This keeps core changes under orchestrator control while still parallelizing
the mechanical test work — the cap-hit child's investigation is the head
start, not wasted budget.

