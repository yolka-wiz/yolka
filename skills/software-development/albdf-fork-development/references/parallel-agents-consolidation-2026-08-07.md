# Parallel fix agents + orchestrator consolidation (M13, 2026-08-07)

## The pattern that failed (and how to recover)

Three fix workstreams (WS-A GUI search wiring, WS-B R#4 core fix, WS-C clipboard
re-inversion) were dispatched in PARALLEL against the SAME `main` checkout. All
three hit their tool-call caps mid-task and returned with honest "not finished"
reports. The working tree held a tangle of uncommitted edits from all three:

```
M src/Pdf4QtLibCore/sources/pdfpagecontenteditorprocessor.{h,cpp}   (WS-B)
M src/Pdf4QtLibCore/sources/pdfrtltextnormalizer.{h,cpp}            (WS-C)
M src/Pdf4QtLibCore/sources/pdftextsearchengine.cpp                 (orchestrator fix)
M src/Pdf4QtLibGui/pdfadvancedfindwidget.cpp                        (WS-A)
M src/Pdf4QtLibWidgets/sources/pdfwidgettool.cpp                    (WS-A + WS-C)
?? src/Pdf4QtLibWidgets/sources/pdfwidgetrtlsearch.{h,cpp}          (WS-A)
?? src/UnitTests/tst_rtlnormalizertest.cpp                          (WS-C)
```

### Recovery procedure (worked, all 16/16 green, 8 logical commits)

1. **Read ALL agent reports first** — each carried a "next steps for the parent"
   section that together formed the consolidation plan. WS-B's report had the exact
   remaining blockers (2 test failures: one stale pin, one sibling interference);
   WS-C's report had the exact 3-line copy-path edit + `#include` to add.
2. **Build core with EVERYTHING in the tree** — the first build failed on WS-C's
   test (`PDFRTLTextNormalizer has not been declared` — missing `pdf::` namespace
   prefix, class is in namespace `pdf`). Fix per-file, rebuild.
3. **Triangulate the 3 failures with fresh eyes**:
   - RtlNormalizer: test INPUT typo (`اببحرم` 7 chars vs correct `ابحرم` 5 chars) —
     the code was right, the test data was wrong.
   - RtlAddText: the test PINNED the old degraded behavior — the R#4 fix makes it
     wrong-by-design; update the pin (fix's intended win, not a regression).
   - SearchText `test_engineSearchSalam`: REAL engine bug (S#3, visual-order lam-alef
     — see `rtl-search-visual-order-lamalef.md`). The test was correct and exposed a
     genuine pre-existing bug the CLI tests never covered.
4. **Apply the missing GUI edits the capped agents designed but couldn't commit**
   (WS-C's `onActionCopyText` re-inversion — 3 lines + include).
5. **Commit in LOGICAL UNITS with explicit paths** — never `git add -A` on a shared
   tree: R#4 core fix → engine fix → normalizer helper → GUI adapter → GUI copy fix →
   test pin update → docs. `python3 scripts/gen-repo-map.py` before the docs commit.
6. **Verify with the FULL loop, not just the new tests**: ctest 16/16, `gui-smoke.sh`,
   CLI `search-text "سلام"` on the fixture (the original bug symptom).

## Lessons for future parallel-GUI work

- **Same-checkout parallel agents CANNOT edit the same files safely.** WS-A and WS-C
  both touched `pdfwidgettool.cpp`; WS-C deliberately did NOT apply its edit to avoid
  clobbering WS-A. For parallel text/GUI workstreams, use separate worktrees per agent
  (like the M10 wave) or serialize the shared-file edits.
- **Capped agents are the NORM, not the exception.** Budget for a consolidation pass:
  the orchestrator must be willing to finish N-1 agents' work from the working tree.
  Treat every agent "done" claim as unverified until you've rebuilt + run the suite
  yourself (this session: WS-A's "link failure" was actually WS-B's uncommitted core
  changes not yet built into the .so — a coordination artifact, not a defect).
- **Distinguish test bugs from code bugs by triangulation**: same recipe failing in
  the test but "working" in CLI → check for measurement traps (grep echo counting),
  then byte-compare artifacts, then probe internals (char rects). Only then trust a
  code-level fix.
