# Parallel sibling agents sharing the working tree (verified 2026-08-07, WS-C)

Hit while WS-C (RTL clipboard copy) ran alongside WS-B (R#4 /ActualText) on the
SAME main checkout. Both agents were editing overlapping files mid-task.

## What happened

- `git status --short` suddenly showed a sibling's uncommitted edits in files
  WS-C also needed: `pdfwidgettool.cpp` (sibling added `pdfwidgetrtlsearch.h`
  include + routed `PDFFindTextTool::performSearch` at ~line 605), plus
  `pdfpagecontenteditor*.{h,cpp}`, `pdfadvancedfindwidget.cpp`,
  `tst_searchtexttest.cpp`, `Pdf4QtLibWidgets/CMakeLists.txt`, and new files
  `pdfwidgetrtlsearch.{h,cpp}`.
- The `patch` tool emitted a warning: "file was modified by sibling subagent
  'sa-1-5f205159' at <time> — after this agent's last read" — the file had been
  changed under me between my read and my write.
- HEAD moved mid-task: `9f5e1338` → `1d7b8c69` (sibling's R#4 RED test commit).

## Detection recipes (all verified)

- **Sibling uncommitted diff in your exact target file:** `git diff <file>` —
  if it shows changes you didn't make, STOP and coordinate; do not patch on top
  blindly (your patch tool may apply against a stale read).
- **Sibling commit landed mid-task:** `git show HEAD:<file> | wc -l` vs
  `wc -l <file>` mismatch, or `git log --oneline -3` showing a commit you
  didn't make. Re-read the file before continuing.
- **The patch-tool sibling warning is authoritative** — when it fires, re-read
  the file (the diff it returns may have been applied against stale content).

## Rules that held

- Stage ONLY your own paths (`git add <my files>`), never `git add -A` — the
  sibling's uncommitted changes must never ride into your commit.
- When a sibling is mid-edit on your target file, either wait, or make your
  edit non-overlapping and re-verify the file state right before writing.
- If your task hits its tool budget before committing, do NOT commit partial
  overlapping work — report the conflict explicitly so the orchestrator can
  reconcile (this session did exactly that; the sibling's diff was intact and
  no clobbering occurred).
