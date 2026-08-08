# Shared-tree fix-consolidation (M13, 2026-08-07)

Parallel fix workstreams dispatched on ONE checkout; all three hit tool caps
leaving an uncommitted, semi-broken tree. Orchestrator consolidated. This is
the worked example for the "Parallel fix agents on ONE shared checkout"
pitfall in SKILL.md.

## What was dispatched

WS-A (GUI RTL search adapter + 2 widget wirings), WS-B (R#4 /ActualText
preservation in the content editor), WS-C (RTL clipboard re-inversion).
All three on the SAME `main` checkout, no worktrees (orchestrator
violated its own isolation rule under time pressure).

## What actually happened

- All three hit ~50 tool-call caps. NONE committed (tree was broken by the
  combined edits; repo rule: every commit must compile).
- WS-B's full-suite run failed with 2 failures caused by WS-C's uncommitted
  normalizer changes + an old test PINNING the buggy behavior (expected
  degraded `ملس`, the fix restores `ملاس`).
- WS-C deliberately did NOT apply its copy-path edit (would clobber WS-B's
  in-flight diff on the same file) and did NOT commit.
- WS-A's GUI link failed on a STALE core .so (WS-B's processor changes not
  rebuilt into it) — a coordination artifact, not an adapter defect.
- Combined tree: 16 modified/untracked files, 3 failing tests
  (UnitTestsRtlNormalizer, UnitTestsRtlAddText, UnitTestsSearchText).

## Consolidation sequence that worked

1. Read ALL three full summaries (truncated inline; full text in
   `cache/delegation/subagent-summary-*.txt`). Classified: WS-B DONE-but-
   uncommitted, WS-A DONE-but-uncommitted (+1 designed-not-applied test
   update), WS-C DESIGNED-but-not-applied (+ core helper done).
2. `cmake --build src/build` with everything in the tree → fixed surface
   errors: WS-C's test called `PDFRTLTextNormalizer::invertToLogical`
   unqualified but the class is in `namespace pdf` → `pdf::` prefix.
3. Full ctest → 3 failures, each diagnosed:
   - RtlNormalizer: test INPUT TYPO (`اببحرم` should be `ابحرم` — 7 chars
     vs the 5-char word), not code.
   - RtlAddText: expectation PINNED the old buggy behavior → update to the
     fixed full ligature + rewrite the comment (the fix's proof).
   - SearchText `test_engineSearchSalam`: 0 matches — genuine PRE-EXISTING
     engine bug (visual-order lam-alef, see pdf-text-engineering S#3), NOT
     caused by any agent. The test was correct to fail; the engine needed
     fixing.
4. Applied WS-C's designed edit myself (3 lines in `onActionCopyText`:
   `if (text.isRightToLeft()) text = PDFRTLTextNormalizer::invertToLogical(text);`
   + the `#include`), per the agent's report.
5. Committed in LOGICAL UNITS with `git add <paths>` per workstream, never
   `git add -A`: R#4 core fix, engine S#3 fix + test, invertToLogical +
   test, GUI search adapter + wiring, GUI copy fix, test-expectation
   update, docs. Each message explained the WHY.
6. Full gate: format gate FAILED on 3 files (hand-formatted by agents) →
   `clang-format -i` + commit `style: clang-format M13 core files`.
   Release gate then `CI: ALL GREEN`.
7. Verified: 16/16 ctest, gui-smoke.sh PASS, `search-text "سلام"` on the
   RTL fixture now finds the match (was 0 — the engine bug).

## Lessons

- Test-expectation drift is the #1 "false regression" in a fix
  consolidation: an old test that pins the buggy behavior MUST be updated
  when the fix lands — that update IS part of the fix.
- A new consumer of an old code path surfaces latent bugs (the GUI adapter
  exposed the lam-alef search gap) — the failing test is the gift, not the
  problem.
- Agents with overlapping-file edits will self-censor (WS-C withheld its
  edit) — the orchestrator must apply designed-but-unapplied edits from the
  reports.
- Check `git branch --show-current` before committing a format fix — a
  child may have left another branch checked out (the fix landed on
  m12/gui-ci and had to be cherry-picked to m12/gui-restore).
