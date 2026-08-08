# R#4 — preserving /ActualText marked content through the content editor (2026-08-07)

Status: fix pattern IMPLEMENTED, new regression test GREEN; suite-wide green NOT
reached before session end (2 unrelated failures, one stale expectation, one
unroot-caused — see Verification). Not a fully closed task.

## Problem

- `add-text --rtl` emits `/Span << /ActualText <FEFF...> >> BDC ... EMC` around
  every RTL run (pdfrtltextengine.cpp:425-433, UTF-16BE+BOM hex payload).
- A second `add-text` (LTR path, pdftooladdtext.cpp:429-493) rebuilds the whole
  page stream through `PDFPageContentEditorProcessor` +
  `PDFPageContentEditorContentStreamBuilder`.
- The upstream editor model had no marked-content knowledge → BDC/EMC silently
  dropped → extraction degrades lam-alef (`لاع` → `لع`).

## Degradation recipe (CLI)

```bash
albdf add-text blank.pdf rtl.pdf --page 1 --x 72 --y 700 --text 'علا' --size 24 --rtl --font Vazirmatn-Regular.ttf --lang fa
albdf fetch-text rtl.pdf            # -> 'لاع'  (intact)
albdf add-text rtl.pdf edited.pdf --page 1 --x 72 --y 600 --text Hello --size 12
albdf fetch-text edited.pdf         # -> 'لع \n  Hello'  (degraded, baseline)
```

## Fix shape (audit-rejected: do NOT add a 4th `PDFEditedPageContentElement::Type`)

**Capture (processor):** `PDFEditedPageContentElementText::Item` gains
`QByteArray actualText` (UTF-16BE+BOM; empty = not a marker). Override
`performMarkedContentBegin(const QByteArray& tag, const PDFObject& properties)`
with the SAME guard as pdftextlayoutgenerator.cpp:91-101 — `tag == "Span"`,
properties dict resolves `/ActualText` to a string, decode via
`PDFEncoding::convertTextString`. Record a marker Item on
`m_contentElementText` (only when the text element exists). Nesting via a small
`std::vector<QByteArray> m_actualTextStack` (push EVERY BDC's decoded text,
empty for non-ActualText BDCs so EMCs pair correctly); record a marker ONLY for
the outermost ActualText span (matches the layout generator's outer-wins
replacement). `performMarkedContentEnd()` just pops — span end is implicit at
the next marker / element end. Base virtuals are no-ops; calling
`BaseClass::` is safe. Requires `#include "pdfdocument.h"` (else
`invalid use of incomplete type 'pdf::PDFDocument'` from `getDocument()`)
and `"pdfencoding.h"`.

**Per-run scoping is REQUIRED (design trap).** `createItemsAsText` serializes
marker items as `<actualText v="HEX"/>` in the itemsAsText XML;
`writeTextCommand` re-emits `EMC` (close previous span) then
`/Span << /ActualText <HEX> >> BDC`; `writeText` emits the final `EMC` before
`ET Q`, tracking `bool m_isActualTextSpanOpen` (reset at the top of writeText).
Why per-run and NOT a single element-level BDC/EMC wrap:
`PDFTextLayoutGenerator` replaces the WHOLE glyph range [startIndex, glyphCount)
between a BDC/EMC pair with the span text. A mixed element (one BT/ET holding
an unmarked LTR run + a marked RTL run, e.g. "abc سلام") wrapped as one span
would replace EVERYTHING with the RTL ActualText → silent "abc" data loss. The
XML marker positions each BDC exactly before its run's Tj.

**UTF-16BE encoding pitfall:** do NOT use `QString::toUtf16()` — it is NATIVE
endianness with BOM (LE on x86). Re-encode manually:
`FE FF` + per QChar `(unicode >> 8) & 0xFF`, `unicode & 0xFF`. This reproduces
the engine's byte format, so the layout generator decodes the re-emitted span
identically (empirically verified via the P1 lam-alef tests).

## Verification

- RED commit `1d7b8c69` (test(core)): `src/UnitTests/tst_actualtexttest.cpp`
  + `UnitTestsActualText` target in `src/UnitTests/CMakeLists.txt`
  (add_executable, TEST_BLANK_PDF/TEST_FONT_PERSIAN compile defs, offscreen
  ENV, `add_dependencies(... albdf)`). Baseline FAIL: `لاع` not found after
  the re-edit.
- Fix compiled; `ctest -R UnitTestsActualText` → 1/1 Passed.
- Full suite (15 targets): 2 failures, suite NOT green:
  1. `UnitTestsRtlAddText::test_rtlKeepsLtrIntact` — **STALE EXPECTATION**:
     asserts the degraded `ملس` and its comment documents R#4 as current
     behavior. Fixing R#4 makes it fail because output is now CORRECT
     (`ملاس`). Update the assertion to the full ligature as part of the fix.
  2. `UnitTestsSearchText::test_engineSearchSalam` — 0 matches; does NOT touch
     the editor path (single RTL add-text, no rewrite); still failed after
     stashing the 4 changed files. Suspected pre-existing / parallel-branch
     interference (shared main worktree carried other agents' uncommitted
     pdfrtltextnormalizer/GUI/tst_searchtexttest changes). NOT root-caused.

## Shared-worktree baseline isolation

On the shared `main` worktree, other agents' uncommitted changes coexist with
yours. To prove a test failure is (not) yours:
`git stash push -m <name> -- <your exact file list>` → rebuild → run the
failing test → `git stash pop`. NEVER bare `git stash` (grabs everyone's
changes), and stage only your paths (`git add <paths>`, never `-A`).
Also verify dispatch-brief claims (e.g. "exclusions missing?") against the
LIVE branch — the R#4 brief suspected ci/run-ci.sh lacked the format-gate
exclusions for the two touched files, but grep found them already present.
