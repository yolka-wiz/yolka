# S#1 — Cross-item RTL search (resolved 2026-08-05)

## Symptom
A phrase split across two adjacent text-flow items returned 0 matches.
Field case: `add-text --rtl "تست نهایی"` on a dense page → docstrum Layout
flow absorbs the first word into the surrounding column item, leaving the
rest as its own item. Content stream is one TJ + one /ActualText span; the
split is purely geometric.

## Root cause
`PDFTextSearchEngine::search()` matched the normalized visual query inside
**each item alone** (`normalizedItem.indexOf(...)` per `flow.getItem(i)`).
A query spanning items could never match, even though
`PDFDocumentTextFlow::getText()` already had a joined-string primitive.

## Why the first test attempts failed (important)
Trying to build a CLI-level regression test (two `add-text` runs then
`search-text`) does NOT work:

- Word-sized gap runs → docstrum MERGES them into ONE item → test passes on
  the OLD engine (invalid RED).
- RTL-correct placement (نهایی left, تست right) → merged. Same problem.
- Wrong RTL order (تست left, نهایی right) → two items, but the joined
  string is nonsense (`تست ییاهن` ≠ visualQuery `یاهن تست`) → fails on the
  NEW engine too (invalid GREEN).
- Large gap (x=250+, gap ~110pt at 24pt) → genuinely two items, but that's
  a column gap, not a phrase — correctly 0 matches after the fix. Not a
  test case.

So a deterministic regression test CANNOT go through the CLI. The fix:
add a **test seam** — `PDFTextSearchEngine::searchFlow(const PDFDocumentTextFlow&, ...)`
takes an injected flow; `search()` builds the flow from the document and
delegates. The unit test hand-builds two adjacent items.

## The fix (GREEN design)
Per page, in `searchFlow()`:

1. Collect text items (`flags & Text`, non-empty), group by `pageIndex`.
2. Sort by y-center; cluster into lines (tolerance `0.5*(hA+hB)`).
3. Sort each line by x ascending — item.text is already the visual glyph
   string, so left-to-right concatenation reconstructs page visual text for
   both LTR and RTL.
4. Geometry-aware separator between consecutive line items:
   - `gap <= 0` → `""` (touching: mid-word continuation)
   - `gap <= 2 * avgCharWidth` → `" "` (word space)
   - else → `"\n"` (hard boundary; queries contain no `\n`, so matches can
     never cross lines/columns → no false positives)
   - `avgCharWidth = (wA + wB) / max(1, lenA + lenB)`
5. Normalize the joined string with a **global char map**; `indexOf` loop
   as before.
6. Map match back: `g0 = globalCharMap[matchIndex]`,
   `g1 = globalCharMap[matchIndex+len-1]`; walk `joinedMap[g0..g1]` building
   `ItemSpan{itemIndex, charBegin, charEnd}` (separator chars → -1, skip).
   `matchedText` built char-by-char incl. spaces; bounding rect = union of
   `characterBoundingRects` across spans (fallback item rect).
7. `Match::spans` (vector, empty for single-item matches) — additive,
   zero regression for existing callers. `itemIndex` = first span.

## CLI output (user chose Option 1)
One row per logical match; Item column shows `first+last` for multi-span
matches (e.g. `2+3` = items 2 and 3); count stays 1. Not one-row-per-span
(that would inflate count).

## Test details
- `UnitTestsSearchText::test_crossItemPhrase`: hand-built flow, item1
  `ییاهن` rect(72,700,67.25,17.53), item2 `تست` rect(150,700,28.64,17.06),
  query `تست نهایی` → 1 match, spans.size()==2, matchedText contains space
  and both words, bbox spans both items.
- `UnitTestsSearchText::test_crossItemNoFalsePositive`: `hello` rect(72,...)
  + `world` rect(400,...) → query `hello world` → 0 matches (288pt gap →
  `\n` boundary).
- Verified RED against the OLD engine by checking out old engine files AND
  stashing the CLI change (the CLI referenced `Match::spans`, which the old
  header lacked → build would fail for the wrong reason otherwise).

## Evidence commands
```bash
export QT_QPA_PLATFORM=offscreen
B=src/build/bin/albdf
# dump flow items the search engine sees (temporary qWarning debug):
$B search-text /tmp/x.pdf "نهایی" 2>&1 | grep S1DEBUG
# word item split check on a dense baseline page:
$B add-text src/tests/fixtures/test-baseline.pdf /tmp/d.pdf \
  --page 1 --x 200 --y 500 --text "تست نهایی" --size 18 --rtl \
  --font src/tests/fonts/Vazirmatn-Regular.ttf --lang fa
$B search-text /tmp/d.pdf "تست نهایی"   # count 1 after fix
```
