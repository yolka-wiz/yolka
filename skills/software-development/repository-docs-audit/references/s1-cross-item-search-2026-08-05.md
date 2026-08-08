# S#1 — Cross-item RTL search: verified repro + design (2026-08-05)

Session artifact for turning an audited known-limitation into a TDD plan with a
**verified** red repro. Repo: yolka-wiz/al-bdf-engine (albdf), RTL PDF search.

## The limitation (PROBLEMS.md S#1)

`search-text` matches a query **inside a single text-flow item only**. A phrase
split across items (e.g. by the Layout flow algorithm on dense pages) returns
count 0, while each single word matches.

## Verified red repro (deterministic, not the dense-page flake)

The dense-page split is hard to reproduce on demand. The deterministic twin:
force the phrase into TWO items yourself with two adjacent `add-text --rtl` runs.

```bash
export QT_QPA_PLATFORM=offscreen
B=src/build/bin/albdf
# run 1: "تست" at x=72
$B add-text src/tests/fixtures/blank.pdf /tmp/a.pdf \
  --page 1 --x 72 --y 700 --text "تست" --size 24 --rtl \
  --font src/tests/fonts/Vazirmatn-Regular.ttf --lang fa
# run 2: "نهایی" at x=150, same line
$B add-text /tmp/a.pdf /tmp/b.pdf \
  --page 1 --x 150 --y 700 --text "نهایی" --size 24 --rtl \
  --font src/tests/fonts/Vazirmatn-Regular.ttf --lang fa

$B recognize-text /tmp/b.pdf   # → 2 objects (separate items)
$B search-text /tmp/b.pdf "تست نهایی"   # → count 0  (RED)
$B search-text /tmp/b.pdf "تست"         # → count 1
```

Verified 2026-08-05: recognize-text shows 2 text objects (`تست` at 72.3/700,
`ییاهن` at 150.3/699.8 — the second is visual order of نهایی), phrase search → 0.

## Root cause

`PDFTextSearchEngine::search()` (src/Pdf4QtLibCore/sources/pdftextsearchengine.cpp)
loops `flow.getItem(itemIndex)` and does `normalizedItem.indexOf(visualQuery, ...)`
**per item**. A query spanning items can never match.

Key existing primitive: `PDFDocumentTextFlow::getText()` already joins all item
texts with `" "` (trimmed) — but the search engine doesn't use it.

## Design that passed review (plan, not yet implemented)

1. **Per-page joined string** from text-flow items in reading order + a global
   char map back to `(itemIndex, charBegin..charEnd)`.
2. **Geometry-aware separator** between consecutive items:
   - same line (y-range overlap) AND touching (`B.left <= A.right + 1.0`) → `""`
     (preserves mid-word splits like می+خواهم)
   - otherwise → `" "` (preserves word boundaries; blocks test+ing → testing)
3. Reuse existing normalize + `indexOf` loop over the joined string.
4. Map match back via `globalCharMap` → walk to spans; union
   `characterBoundingRects`; `matchedText` = concatenation across spans.
5. **Additive struct change**: `Match::spans` (`std::vector<ItemSpan>`), empty
   for single-item matches → zero regression/CLI change for existing behavior.
   `Match::itemIndex` stays = first span's index.
6. **False-positive control**: per-page only (never across pages); far-apart
   items must stay 0 (explicit test twin).
7. CLI item column for multi-item: default `2+3` (one row, count stays 1);
   alternative is one row per span (count becomes 2) — user decision, open at
   plan time.

## Files touched (plan)

`src/UnitTests/tst_searchtexttest.cpp` (+2 slots), `pdftextsearchengine.{h,cpp}`,
`src/PdfTool/pdftoolsearchtext.cpp`, `docs/PROBLEMS.md`, `README.md`,
`docs/albdf.1`, `docs/RELEASES.md`, `db/seed.py`.

## Resume pointer

Full TDD plan (tasks 1–5, commit-per-task): `.hermes/plans/2026-08-05_150000-s1-cross-item-search.md`
