# RTL search: visual-order lam-alef collapse (S#3, 2026-08-07)

## Symptom

`PDFTextSearchEngine::search(&document, u"سلام", 0, 0)` returned 0 matches for a
document created by `albdf add-text --rtl --text "سلام" ...`, while:

- `albdf search-text doc.pdf "س"` → **1 match** (single char works)
- `albdf search-text doc.pdf "لا"` → "1 match" — but this was a **measurement trap**:
  the query itself collapses `لا`→`ل`, so it matched the lone `ل` in the flow, not
  the ligature. `grep -c "سلام"` on search-text output counts the QUERY ECHO line,
  so naive greps "confirmed" matches that the `Matches` table showed were absent.
- `albdf search-text doc.pdf "سلام"` → 0 matches (the real state)
- Hebrew `שלום` → 1 match (works — no lam-alef in Hebrew)

## Root cause

The engine normalizes the QUERY in **logical** order (`لا`→`ل` collapse →
`سلام`→`سلم`, 3 chars), then inverts to visual. But the extracted FLOW text is in
**visual** order (leftmost-first): `مالس`. In visual order the lam-alef ligature
appears as the REVERSED pair `ال` (ا then ل), which the logical-order collapse rule
(`cp==0x0644 && next==0x0627`) never sees — the flow kept 4 chars, the query had 3,
never matched.

Why it survived until M13: all existing search tests either (a) used the
`searchFlow()` test seam with hand-built flows, or (b) searched words WITHOUT
lam-alef (`محمد`, `دنیا`, `שלום`). Document-level `search()` had zero lam-alef
coverage. The GUI search adapter (M13) was the first consumer of the document-level
path — its new test `test_engineSearchSalam` exposed the bug.

## Why not just collapse `ال` always?

In LOGICAL order, `ال` (ا then ل) is the Arabic **definite article** (السلام = al-salam)
and must NOT collapse. The collapse rule is direction-dependent:
- logical `لا` (ل then ا) → ligature → collapse to `ل`
- visual `ال` (ا then ل) → ligature seen reversed → collapse to `ل`
- logical `ال` → article → keep

## Fix (`4cabbf7a`)

1. `PDFRTLTextNormalizer::Options` gains `bool visualOrder = false`.
2. In `normalize()`, the lam-alef branch collapses `ال`→`ل` when
   `options.visualOrder && cp==0x0627 && next==0x0644` (in addition to the existing
   logical `لا`).
3. In `PDFTextSearchEngine::searchFlow`, the FLOW-side normalization (step 3) copies
   `options.normalizer` and sets `visualOrder = true`; the QUERY-side normalization
   (step 1) stays logical. Comment explains both sides must collapse the ligature the
   same way.

## Verification

- New test `test_engineSearchSalam` (`src/UnitTests/tst_searchtexttest.cpp`): builds
  doc via `add-text --rtl`, loads via `PDFDocumentReader`, asserts
  `engine.search(&document, u"سلام", 0, 0).size() == 1` + negative control
  `شلام → 0`.
- All 12 pre-existing search tests still pass (no article false-positive).
- Full suite 16/16 green; CLI `search-text "سلام"` on the fixture now returns 1.

## Debug path (reusable for "engine works in CLI but not in test")

1. Reproduce the exact CLI recipe manually — it WORKED, the test failed on the same
   recipe. Then re-run CLI on the TEST's kept tmpdir file
   (`tmpDir.setAutoRemove(false)`) — **CLI also returned 0**. The earlier "CLI works"
   reading was the grep-echo trap.
2. Both files were byte-identical (same sha256 = the fixture). So the divergence was
   not the file.
3. Probe the flow geometry: a tiny C++ probe linking `libPdf4QtLibCore`
   (`PDFDocumentTextFlowFactory::create(..., Algorithm::Layout)` then dump
   `item->text` + `characterBoundingRects`) showed flow text `مالس` with 5 char rects —
   the lam-alef stored as two separate glyphs, `ال` in visual order.
4. Single-char and non-ligature searches matched → the text was IN the flow; the
   phrase spanning the lam-alef didn't. Direction-of-collapse mismatch identified.

## Also fixed alongside (orchestrator consolidation, same working tree)

- RtlNormalizer test had a wrong visual input `اببحرم` (7 chars) instead of `ابحرم`
  (5 chars = reversed `مرحبا`) — test typo, not code bug.
- `tst_rtladdtexttest.cpp::test_rtlKeepsLtrIntact` pinned the OLD degraded behavior
  `ملس`; after R#4 fix it must expect the full ligature `ملاس` (see
  `content-editor-actualtext-r4-2026-08-07.md`).
