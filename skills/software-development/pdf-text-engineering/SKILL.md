---
name: pdf-text-engineering
description: "Use for PDF/RTL text, search, and write pipelines (albdf)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pdf, rtl, search, text-extraction, albdf, pdf4qt, harfbuzz, fribidi]
    related_skills: [qt-cmake-vcpkg-build, test-driven-development, systematic-debugging, plan]
---

# PDF Text Engineering (albdf / PDF4QT fork)

Headless PDF text work on the albdf repo (`yolka-wiz/al-bdf-engine`, fork of
MIT PDF4QT, GPL-3.0 authored additions). Covers extraction, RTL-aware search,
and the add-text write pipeline. Build/test details live in
`qt-cmake-vcpkg-build`; this skill is about the PDF text model itself.

## Core model (the #1 thing to remember)

PDF content streams store text in **VISUAL order** (as glyphs appear
left-to-right on the page). Users think in **LOGICAL order**. Every text
feature is a bridge between the two:

- `add-text --rtl`: logical → FriBidi runs → HarfBuzz shaping → visual-order
  glyphs in the content stream, with `/ActualText` marked content carrying
  the logical string for extractors.
- `search-text`: user query (logical) → `invertToVisual()` via
  `fribidi_log2vis` → match against extracted visual-order text.
- **RTL first logical word sits RIGHT.** "تست نهایی" = نهایی LEFT, تست RIGHT.
  Each word's glyphs are also reversed (`نهایی` extracts as `ییاهن`).

## docstrum Layout flow — why CLI tests can't reproduce everything

`PDFDocumentTextFlowFactory::create(..., Algorithm::Layout)` (docstrum)
**merges adjacent same-line runs into a single item** on sparse/synthetic
pages. Consequences:

- Two `add-text` runs with a word-sized gap land as ONE flow item — so a
  CLI-level cross-item search test is impossible to build that way.
- A large gap (column-sized, ~2×+ char width) DOES produce two items — but
  that is not a phrase, and joining it would be a false positive.
- The genuine field split (one run split at a word boundary on a dense page,
  first word absorbed into surrounding column text) only happens on
  real-world dense PDFs, not synthetic blanks.
- Flow item order is NOT guaranteed visual order. `item.text` IS the visual
  glyph string; for search you must sort items by x ascending within a line
  cluster, not trust flow order.

**Consequence:** to test cross-item behavior deterministically, use the
engine's **test seam**: `PDFTextSearchEngine::searchFlow(flow, ...)` accepts
an injected `PDFDocumentTextFlow`. Build the two adjacent items by hand in
the unit test (see `references/s1-cross-item-search.md`).

## Search: joined visual string + spans

`PDFTextSearchEngine::searchFlow()` (src/Pdf4QtLibCore/sources/pdftextsearchengine.cpp):

1. Group text items per page; cluster into lines by y-center
   (tolerance `0.5*(hA+hB)`); sort each line by x ascending.
2. Join with a **geometry-aware separator**:
   - touching runs (`gap <= 0`) → `""` (mid-word split: می+خواهم)
   - word-sized gap (`gap <= 2 * avgCharWidth`) → `" "`
   - between LINE clusters: **soft boundary** — when the vertical gap
     (`curLineTop − prevLineBottom`) is `<= 0.5 × max line height`
     (paragraph-like leading), join with `" "` so a space-bearing phrase
     can span the line break; larger gaps (column separation) keep
     `"\n"`, a **hard boundary** the query can never cross (queries have
     no newline). Within a line, column-sized x-gaps also emit `"\n"`.
     Landed 2026-08-06 (commit `0cf3338`); the match walk already
     appends `' '` separators to `matchedText`, so span mapping needs no
     change.
3. Normalize the joined string with a global char map, match with
   `indexOf` repeatedly, then map matches back to
   `(itemIndex, charBegin..charEnd)` **spans** (Match::spans; empty for
   single-item matches). Bounding rect = union across spans.

Always ship a **no-false-positive twin test** (far-apart items → 0 matches)
next to the cross-item positive test.

## Visual-order lam-alef collapse (S#3) — document-level search missed `سلام`

**Fixed 2026-08-07 (`4cabbf7a`, M13).** `PDFTextSearchEngine::search()`
(5-arg, document-level — the path the GUI adapter uses) could NOT find
words containing lam-alef (`سلام`) in `add-text --rtl` output, while
`searchFlow()` (test seam) passed. Root cause is the asymmetry between the
two normalizations:

- **Query side (logical):** `سلام` → `PDFRTLTextNormalizer::normalize`
  collapses `لا` (U+0644 U+0627) → `ل` → `سلم` (3 chars) → inverted to
  visual `ملس`.
- **Flow side (visual):** the extracted text is `مالس` (4 chars) — the
  lam-alef ligature appears as the REVERSED pair `ال` (U+0627 U+0644), so
  the logical-only `collapseLamAlef` never fires. 3-char query vs 4-char
  flow → 0 matches.

**Fix:** `PDFRTLTextNormalizer::Options` gained `bool visualOrder = false`.
When set, `collapseLamAlef` ALSO collapses `ا`+`ل` → `ل`. The engine enables
`visualOrder` ONLY for the flow-side normalization (step 3); the query side
(steps 1) stays logical. Existing tests still pass because the article
`السلام` case (logical `ال` = article, never collapsed on the query side)
is unaffected — the flow side collapses both spellings to the same `ل`.

**Why it was invisible for so long:** every existing engine test used the
`searchFlow` seam with hand-built flows, and the CLI-level tests searched
words WITHOUT lam-alef (`محمد`, `دنیا`, `שלום`). The GUI search adapter
(M13) was the first consumer of document-level `search()` on a lam-alef
word — the regression `test_engineSearchSalam` (in `UnitTestsSearchText`)
pins it. Lesson: when a new API consumer exercises an old code path on a
different input family, expect it to surface latent bugs the original tests
never covered.

**Measurement trap that prolonged the debug:** verifying CLI search output
with `search-text <file> "سلام" | grep -c "سلام"` counts the QUERY ECHO
line in the result header, NOT matches — `grep -c` returns 1 even when the
match table is empty (the header always prints the query). Parse the actual
`Matches` table or the `count:` line; never grep for the query string
itself. Also: `search-text` output's `count=` is the true match count —
trust it over eyeballing rows.

## GUI search/select/copy paths vs the engine (vendored GUI layer, M12)

The GUI layer (`ALBDF_BUILD_GUI=ON`) does NOT use `PDFTextSearchEngine` anywhere.
Both search widgets call `PDFTextLayoutStorage::find` → `PDFTextFlow::find` →
`m_text.indexOf` (plain substring; pdftextlayout.cpp:1353) — no visual inversion, no
normalization, per-flow only (no cross-line). By contrast, GUI selection/copy
(`PDFTextLayout::getTextFromSelection`, pdfwidgettool.cpp:882) DOES get `/ActualText`
ligature repair for free because the layout is built by `PDFTextLayoutGenerator`
(pdfcompiler.cpp:574-576), which applies the overlay (pdftextlayoutgenerator.cpp:132).
So: **repair reaches copy/extraction automatically; RTL-aware search does not reach the
GUI at all.** When wiring it in: both widgets already store `pdf::PDFFindResults`
(matched/context/textSelectionItems at pdftextlayout.h:304-317), so an adapter mapping
engine `Match` → `PDFFindResult` drops in with zero downstream changes; build the flow
items from the existing storage layout mirroring `pdfdocumenttextflow.cpp:709-714`.
`PDFRecognizeText` (CLI-only) also bypasses the repair for its `info.text` (raw stream
chars, pdfrecognizetext.cpp:166-185). Full verified map (all 6 paths, file:line, call
chains, minimal wiring, P0/P1/P2 list): `references/gui-text-paths-audit.md`.

**M13 LANDED the GUI search wiring (2026-08-07).** New adapter
`src/Pdf4QtLibWidgets/sources/pdfwidgetrtlsearch.{h,cpp}` —
`pdf::searchDocumentPlainTextRTL(document, textLayoutStorage, query, caseSensitivity, pageFirst, pageLast)`
builds the flow via `PDFDocumentTextFlowFactory::create(..., Algorithm::Layout)` (the
engine's own document path), calls `PDFTextSearchEngine::searchFlow`, and maps each
`Match` → `PDFFindResult`: `matched = match.matchedText`; `textSelectionItems` via
`PDFTextLayout::createTextSelection(pageIndex, boundingRect.topLeft(),
boundingRect.bottomRight())` on a COPY of the widget's layout (createTextSelection
mutates the layout — mutating the compiler's shared layout is a data race with the
compile thread); `context` = flow-text neighborhood. Both widgets call it in their
PLAIN-TEXT branch only (`PDFFindTextTool::performSearch` pdfwidgettool.cpp:571,
`PDFAdvancedFindWidget::performSearch` pdfadvancedfindwidget.cpp:237) — regex /
whole-word / wildcard stay on legacy `storage->find`. Sort, `PDFFindResults` storage,
and highlight rendering untouched. Commit `088c1b09`; the GUI search now benefits from
normalization + visual inversion + cross-line joining, AND the S#3 visual-order
lam-alef fix (4cabbf7a) applies. Headless verification is CLI-side
(`albdf fetch-text` / `search-text` on the fixture) because the GUI apps expose no
headless text-export flag.

## Write pipeline: TJ spacing is horizontal-only

`pdfrtltextengine.cpp` emits glyphs as one `[<hex> <adjust> <hex> ...] TJ`.
- `xOffset` (GPOS kerning/mark x) folds into a numeric TJ adjustment.
- **`yOffset` cannot be expressed as TJ spacing** — vertical mark offsets
  (fatha/kasra/damma, niqqud) are silently dropped; marks paint at the
  baseline. This is P3, fixed via **text rise (`Ts`)** per mark glyph
  (PDF 32000-1 §9.4.2): `rise = -yOffset * fontSize / upem` (H1, 'f' 2 —
  fatha y_off −146 @24pt/2048 → `1.71 Ts`), emit `rise Ts`, mark glyph as
  a single-glyph `<hex> Tj`, `0 Ts`. Never split the run with `Tm` —
  PDF4QT inserts a phantom space at Tm boundaries, breaking extraction.
  **Ts is a text-state operator: it can ONLY appear between CLOSED TJ
  arrays.** The working emitter flushes the pending hex, emits
  `[<items>] TJ`, then `rise Ts / <hex> Tj / 0 Ts`, then re-accumulates
  the remaining glyphs into a fresh TJ. Emitting Ts while the array is
  still being collected yields INVALID `[<hex> 1.71 Ts ...] TJ`. Exact
  structure + emitted streams for `مَا`/`بِسْم`:
  `references/p3-phase2-investigation.md`. Execution is orchestrated: DB
  task #19 (rtl-writer), `plans/P3-execution.md` (4 phases: RED pixel-probe
  test → GREEN Ts emission → no-regression fetch/search → docs/DB close +
  CI + push). See `references/p3-vertical-mark-offsets.md`.
  Renderer source confirms the unit convention: `drawText()` in
  pdfpagecontentprocessor.cpp builds `adjustMatrix(..., textRise)` with the
  rise UNSCALED by fontSize (glyph paths are pre-scaled; `Tm` carries no
  scale) — so emit the point displacement `-yOffset * fontSize / upem`, not
  `yOffset/upem`.
- **P6 SUPERSEDES the "RealText blob" theory — VERIFIED root cause is the
  CIDToGIDMap, not the renderer.** Earlier probes saw a ~14px "oversized
  mark blob" and blamed the RealText drawText path; that was a
  misdiagnosis (see Pitfalls). The REAL cause, proven with Ghostscript +
  fontTools (2026-08-05): the emitter writes `/CIDToGIDMap` as a SHORT
  ARRAY (`[0 681]` for one glyph, `[0 1173 728 1266]` for three). PDF
  32000-1 §9.7.4.3 requires **65536 entries** (or a stream) for a
  2-byte-CID font. Strict renderers (Ghostscript) reject the short array →
  Identity fallback (CID == GID) → code 1 = GID 1 = `.null` (INVISIBLE),
  code 2 = GID 2 = **Latin 'A'**. So the "14px mark blob" was literally the
  letter 'A', and a single-glyph "ا" PDF renders BLANK in Ghostscript.
  PDF4QT's parser only reads CIDToGIDMap when `isStream()` (pdffont.cpp
  ~2354) — albdf's own renderer ignores arrays too, so ALL RTL output maps
  wrong glyphs in every renderer. **Fix (LANDED, commit 74a1166,
  2026-08-05): emit a 65536-entry stream, 2-byte big-endian, entry[0]=0
  (.notdef), entry[code]=gid, unused=0 (131072 bytes raw), Flate-compressed
  via `PDFFlateDecodeFilter::compress` (`<< /Length N /Filter /FlateDecode
  >>`, FontFile2 pattern).** Verified on the REAL emitter: "ا" → 152B stream
  → 131072B, entries {1: 681}; "مَا" → 159B → {1: 1173, 2: 728, 3: 1266};
  BOTH renderers paint correct glyphs (Ghostscript alef 2×16px/32 ink, albdf
  render identical; مَا composites 16×17/93 GS vs 16×16/76 albdf). Probe
  with `scripts/cidtogidmap_probe.py`; detail: `references/p6-cidtogidmap-fix.md`.
  The Ts mechanism itself is mechanically correct (gid 728
  + `Ts 2` rises 2px in Ghostscript); it was unverifiable by pixel probes
  until the glyph mapping was fixed. Fix order: CIDToGIDMap stream FIRST
  (P6), then re-verify Ts (P3) with correct glyphs.
  **Kasra direction RESOLVED (P3 landed 2026-08-05, commits 109a4af /
  9a4587d / 4ed7ab2): never infer mark direction from the sign of
  y_offset alone** — both fatha (−146) and kasra (−335) are negative yet
  move OPPOSITE ways. The correct sign comes from where the mark glyph's
  INK sits relative to its origin: query `hb_font_get_glyph_extents`
  once per code during shaping (hbFont is alive there; at emission time
  it is destroyed) and store a `bool inkAboveOrigin` on the ShapedGlyph.
  fatha ink y 1141..1410 (above origin) → POSITIVE Ts (up); kasra ink
  y −505..−236 (below origin) → NEGATIVE Ts (down). Emit
  `rise = inkAbove ? +|yOffset|*fontSize/upem : -|yOffset|*fontSize/upem`,
  rounded 'f' 2. Also landed: the phantom-space flow guard (see
  Pitfalls — zero-advance marks must not trigger the space heuristic)
  and the kasra test-band recalibration from ink extents. Full landed
  state + A/B/C isolation proof: `references/p3-ts-emission-complete.md`.
  Full evidence chain (emitted dicts, Ghostscript pixel
  numbers, gid→shape table, patch recipe):
  `references/p6-cidtogidmap-spec-compliance.md`. Older pre-fix numbers:
  `references/p3-phase2-investigation.md`.
- Zero-advance mark glyphs must stay INLINE (no numeric TJ item) — a
  numeric item creates a pen gap that flow heuristics turn into a phantom
  space.

## Redact command (DB #29) — annotation-driven, NO rect/page flags

`albdf redact <input> <redacteddocument>` (upstream `pdftoolredact.{h,cpp}` +
`pdf::PDFRedact`) has **no `--page`/rect/selection flags** — only
`--redact-copy-title|metadata|outline`. Redaction regions come exclusively
from **Redact annotations** (`/Subtype /Redact`) already embedded in the
SOURCE document: `PDFRedact::perform()` iterates each page's annotations,
unions `PDFRedactAnnotation::getRedactionRegion()` (from `/QuadPoints`;
`parseQuadrilaterals` falls back to `/Rect` when QuadPoints is absent), then
`PDFPrecompiledPage::redact(path, matrix, Qt::black)` **subtracts the region
from every DrawPath instruction** (glyph outlines are paths) and overpaints a
black fill. Pages are rebuilt via `PDFDocumentBuilder`, so the annotations
themselves are dropped. Consequences:

- A fixture WITHOUT Redact annotations redacts to a **no-op** (exit 0,
  copy-like output, text survives). Any test proving removal needs a fixture
  that CARRIES a Redact annotation — build it with the repo's deterministic
  `pdfgen.py` (page dict gets `/Annots [<n> 0 R]`; annotation dict =
  `<< /Type /Annot /Subtype /Redact /Rect [x1 y1 x2 y2] >>`).
- **VERIFIED (2026-08-06): the output text layer is GONE ENTIRELY.** Pages
  are re-serialized through `PDFContentStreamBuilder` (QPdfWriter-backed);
  `compiledPage.draw()` emits even text glyphs via `painter->drawPath(...)`,
  so QPdfWriter bakes ALL glyphs to VECTOR CURVES. `fetch-text` on a redacted
  output returns NOTHING — even for pages/lines far outside the region.
  Verified with real output: fixture with 4 lines → fetch-text before shows
  all 4; after redact → empty. So a "public line survives" assertion FAILS
  by design. Pin "redaction did something" with **render-pixel evidence**
  instead: at 72 dpi, the redaction region's near-black fraction goes from
  ~5% (text-only ink) on the input render to **100% (solid black fill)** on
  the output render, while regions OUTSIDE the redaction rects still render
 non-black content. **Never assert ANYTHING via fetch-text on redacted
 output — it passes vacuously (all strings are "absent" because the whole
 layer is gone).** Landed integration suite (DB #29, 2026-08-06,
 `UnitTestsRedact`/`tst_redacttest.cpp`, commit 3a7568b, ctest 13/13):
 scanline near-black fraction **≥ 0.95** inside each `/Rect` on the output
 render — with an **input-sanity guard** (the input regions must NOT already
 be bars, or the assertion is vacuous) — and public scanlines outside the
 rects keep their input black fraction (±0.03). Plus page size preserved
 (612x792 @72dpi), `info` round-trip (exit 0, page count 1), byte-determinism
 (two runs → same sha256), and exit-code contract (missing output → 7
 `ErrorInvalidArguments`, nonexistent input → 4 `ErrorDocumentReading`).
 Full recipe + coordinate math: `references/m10-redact-test-suite.md`.
- **DETERMINISM BUG (FIXED 2026-08-06, commit `e79bc06`):** `albdf redact`
  output was NOT byte-deterministic. `PDFRedact::perform` rebuilds via
  `PDFDocumentBuilder::createDocument()`, whose `createTrailerDictionary`
  (pdfdocumentbuilder.cpp:5383-5387) stamped the `/Info` dict's
  `CreationDate`/`ModDate` with `QDateTime::currentDateTime()`
  (`WrapCurrentDateTime()`). Two runs 3 s apart → different sha256 (byte-diff
  shows ONLY the date strings differ, `D:YYYYMMDDHHMMSS`). Same-second
  back-to-back runs are byte-identical → a naive determinism test is FLAKY
  (passes by luck inside one second). Prove/detect with sleep-separated runs;
  `pdftoolunite` (pdftoolunite.cpp:78) shares the same builder path and was
  fixed by the same change. **The fix (landed `e79bc06`) made the factory
  deterministic: honor `SOURCE_DATE_EPOCH` if set (reproducible-builds
  convention, same as scripts/package.sh), else FIXED epoch
  1970-01-01T00:00:00Z — never wall-clock.** One factory
  (`PDFObjectFactory::operator<<(WrapCurrentDateTime)`) feeds all ~13 date
  sites (trailer Info, signatures, annotations), so fixing it fixed them all.
  Verified: two redact runs 3 s apart → identical sha256; full ctest 12/12
  green. Repo contract: AGENTS.md §2.1 "no QDateTime::currentDateTime() in
  document output".
- Unknown flags are rejected by `QCommandLineParser` at `parser.process()`
  (error path, non-zero exit) — the plan's `redact ... --page 1` smoke
  command is invalid as written.

Full walkthrough + fixture recipe + verification status:
`references/m10-redact-verification.md`. Landed pixel-test suite recipe
(scanlines, thresholds, coordinate math, test-by-test):
`references/m10-redact-test-suite.md`.

## CLI fuzz harness (DB #30, M10 wave-2)

`scripts/fuzz.sh` (repo root, `albdf-fuzz-v1` key=value summary, mirrors
`scripts/benchmark.sh` style) fuzzes the CLI deterministically: regenerates the
`make-*.pdf.py` fixture corpus (hash-checked vs committed fixtures →
`generator_reproducible=` line), derives 10 seeded mutation types from
`random.Random(seed)` (truncate, zero-fill, bit flips, garbage headers,
junk/empty files, self-concat, prepend/append), and runs
info/fetch-text/search-text/add-text/delete-object/delete-page/rotate/move-page/
redact/render on every mutation with a per-invocation `timeout --kill-after=5`,
plus ~27 abusive CLI-arg cases on valid docs (oversized/negative/empty args).
Crash policy per the exit-code contract: signal death (exit ≥ 128) or timeout
kill (124/137) = finding; nonzero exits on corrupt input (4/7) are contract
behavior, recorded not failed. The run continues after crashes (all findings
in one pass) and stops after `--max-hangs` (default 3) or `--max-time`.
Exit 0 = PASS, 1 = crash/hang/harness error, 2 = usage. Reproducers (input
`.pdf` + stderr `.log` + exact command `.cmd`) land in `<work-dir>/fail/` and
the work-dir is retained on failure. Same seed → same corpus → byte-identical
summary; failure paths are stored RELATIVE to the work-dir to keep the
determinism gate work-dir-independent. Full architecture, verification
recipes, and extension guide: `references/m10-fuzz-harness.md`.

**Findings F#1/F#2 (2026-08-06, seed 20260806) — FIXED, do NOT re-fix.** Both
were on VALID input with abusive CLI args; the 500 corpus-mutation cases
crashed nothing (parser is robust to malformed bytes). Fixed by the
render-args dispatch (RED `1e82591` → GREEN `7a70767`, DB #32/#33, all three
reproducers now exit 7 instantly):
- **F#1 CRASH (FIXED):** `render <valid.pdf> --page-first 0 ...` (also
  `--page-last 999999999` with valid `--page-first`) → SIGABRT (134), uncaught
  `std::out_of_range` (`__n = 18446744073709551615` = `(size_t)-1`) thrown
  from a Qt Concurrent worker thread → `terminate`. Root cause:
  `PDFClosedIntervalSet::parse` (pdfutils.cpp) treated `first`/`last` as
  DEFAULTS for open-ended ranges and never validated explicit bounds — the
  header doc promises `[first,last]` enforcement, the code didn't do it.
  `0-1` → interval [0,1]; `1-999999999` → ~1e9-element unfold; after
  `getPageRange` does `--index`, index `-1` hits `PDFCatalog::getPage` →
  `m_pages.at(index)` THROWS inside the worker. Fix: `parse()` now rejects
  bounds outside `[first,last]` with a clear error; every caller already
  maps parseError → `ErrorInvalidArguments` (7). Masked when the
  `--image-output-dir` is missing (exit 7 pre-check runs first).
- **F#2 HANG (FIXED):** `--image-res-dpi >= 10000` → effectively never
  completes (612×792 pt page at 10k dpi ≈ 85k×110k px; ~94 GP at 999999 dpi).
  The 72..6000 DPI clamp (`qBound`, pdftoolabstractapplication.cpp:1026-1040)
  is NOT enough — 6000 dpi on Letter = 51000×66000 px ≈ 13.5 GB RGBA. Fix:
  `pdftoolrender.cpp` computes each page's image size BEFORE rasterization
  (shared `imageSizeGetter` lambda) and rejects any render exceeding
  `PDFPageImageExportSettings::getMaxPixelResolution()` (16384×16384) with
  exit 7.
- Regression suite: `UnitTestsRender` (`tst_rendertest.cpp`, 5 tests:
  page0/huge-last error codes, huge-dpi completes in time, positive control
  render, determinism) wired into ctest → 13/13 green. NOTE: the fix touched
  two pristine vendored upstream files (pdfutils.cpp, pdftoolrender.cpp);
  they were added to the ci/run-ci.sh format-gate AUTHORED_FILES exclusion
  list (their pristine content already fails the repo's .clang-format —
  upstream formatting differs; existing policy excludes modified
  upstream-derived files).

## Pitfalls (learned the hard way)

- **A pre-existing-validation exit can MASK a crash behind it.** `albdf
  render` with a missing `--image-output-dir` exits 7 BEFORE the page-range
  code runs, so probing `--page-first 0` (which SIGABRTs once the dir exists)
  looks clean. When probing a CLI for crashes, satisfy all prerequisite args
  first (mkdir output dirs, valid values for unrelated flags) — otherwise the
  probe validates the early exit, not the code path you targeted.
- **Crash-vs-hang classification can be timeout-timing dependent.** The same
  buggy op (`render --page-last 999999999`) classified CRASH (134) at
  `--timeout 20` but HANG (124) at `--timeout 3` — the worker either aborts
  or spins. Verify a fuzz harness with "findings exist in BOTH classes"
  assertions; never hard-code per-timeout counts.
- **Determinism-gated harness summaries must not embed the absolute work-dir
  path.** First determinism check failed only because `failure=` lines
  contained `/runA/...` vs `/runB/...`; storing input/repro paths RELATIVE to
  the work-dir made summaries byte-identical across work-dirs. Same rule
  applies to any "two runs, same seed → identical output" gate: keep
  timestamps, machine paths, and work-dir paths out of the compared artifact.
- **A back-to-back determinism test is FLAKY when the writer stamps wall-clock
  time — prove determinism with sleep-separated runs.** albdf outputs rebuilt
  via `PDFDocumentBuilder::createDocument()` (redact, unite) embed
  `CreationDate`/`ModDate` from `QDateTime::currentDateTime()` in the `/Info`
  dict (createTrailerDictionary, pdfdocumentbuilder.cpp:5383-5387). Two runs
  in the same second hash identical (naive tests pass by luck); two runs 3 s
  apart differ (byte-diff: ONLY the two `D:YYYYMMDDHHMMSS` strings change).
  Detection recipe: `redact in.pdf a.pdf && sleep 3 && redact in.pdf b.pdf &&
  sha256sum a.pdf b.pdf`, then byte-diff to isolate the source. **FIXED
  (2026-08-06, `e79bc06`)**: the builder now emits `SOURCE_DATE_EPOCH` (if
  set, matching scripts/package.sh) else a fixed epoch — never wall-clock.
  The fix is in `PDFObjectFactory::operator<<(WrapCurrentDateTime)`, which
  covers all date sites (trailer Info, signatures, annotations).

- **The phantom space in search after Ts was a FLOW heuristic bug, not the
  emitter.** When the Ts fix shipped (P3 GREEN), `search-text "ما"` broke:
  fetch-text showed `اَ م` (phantom space). Root cause: upstream
  `PDFTextFlow::createTextFlows` (pdftextlayout.cpp ~1385) inserts a word
  gap when the Euclidean distance between consecutive characters exceeds
  `1.2 × previous.advance`. A zero-advance mark raised by Ts has
  `advance == 0`, so ANY vertical rise (> 1.2×0) looks like a gap →
  phantom space inside a single word → search fails. **Fix (LANDED,
  commit 9a4587d): skip the space guess when the previous character has
  zero advance** (a combining mark is part of the previous word's cluster
  and can never start a word gap). Do NOT switch to horizontal-only
  distance — that breaks 90°-rotated text whose characters carry real
  (vertical) advances but ~0 horizontal gap (smoke test
  `overlap-text.pdf` catches it). A/B/C isolation proof (single TJ vs
  split+Ts vs split-noTs): `references/p3-ts-emission-complete.md`.
- **`.toUpper()` on the whole stream line silently emits `TJ` instead of
  `Tj`.** `QStringLiteral("<%1> Tj\n").arg(code, 4, 16, ...).toUpper()`
  uppercases the OPERATOR too → `<0002> TJ` (array-show with no array!)
  — the mark never paints and the test fails with "no visible ink
  difference" instead of the real band assertion. Uppercase ONLY the hex:
  `.arg(QStringLiteral("%1").arg(code, 4, 16, QLatin1Char('0')).toUpper())`.
- **Kasra test band must come from ink extents, not from the pen offset.**
  The original `+3` band assumed the kasra ink sits at the glyph origin
  (~3.9pt below baseline → rows ~96). With correct glyphs the kasra ink
  hangs BELOW its origin (ink box y −505..−236 font units), so the −3.93
  Ts rise lands it at rows ~99..102 vs base bottom ~98..99 — one row short
  of `+3`. Recalibrated to `+2` with a comment documenting the ink-box
  geometry (commit 4ed7ab2). When a mark's rendered position disagrees
  with the predicted band, check the glyph ink bbox (fontTools BoundsPen)
  — the ink rarely sits at the origin.
- **pypdf stream replacement vs raw byte patching of PDF streams.**
  Raw `re.sub(rb'stream\r?\n(.*?)endstream', ...)` leaves the stream's
  `/Length` stale: Ghostscript tolerates it (scans for `endstream`) but
  PDF4QT reads `/Length` → "Invalid page contents" / NO INK in albdf
  render. For PDF-variant experiments, rewrite streams via pypdf
  `DecodedStreamObject` + `page[NameObject('/Contents')] = stream` so
  `/Length` is fixed; both renderers then agree.

- **`QT_QPA_PLATFORM=offscreen` is mandatory** for every headless
  CLI/ctest invocation; without it `albdf` segfaults (exit 134).
- **`albdf render` needs a pre-existing output dir** (exit 7: "Target
  directory ... doesn't exist" — it does NOT mkdir) and overwrites
  `Image_1.png` per run — `mkdir -p` and use a SEPARATE dir per PDF. The
  `QCommandLineParser: option not defined: "render-software"` /
  `Uknown bool value ''` stderr noise on render is harmless.
- **PDF y-up → image y-down at 72 dpi: sample the GLYPH BAND, not the
  baseline.** `image_y = page_height - pdf_y`; a 24pt line's ink sits at
  `image_y ∈ [baseline_img_y-17, baseline_img_y-1]` (ascenders only), so a
  scanline at the baseline or just below reads 0% black and makes a
  text-present assertion fail confusingly. Locate ink bands empirically
  first (row-scan for luminance < 60, group contiguous rows), then pick
  scanlines. A redaction `/Rect [x1 y1 x2 y2]` (y-up) maps to image rows
  `[page_h - y2, page_h - y1)`, and the text band sits INSIDE that range.
- **Duplicate-yeh collapse shifts the char map start**: normalizing `ییاهن`
  → `یاهن` means the first `ی` maps to the *last* original index, so
  `matchedText` may drop the leading char. Assert on a substring, not the
  full visual string.
- Normalizer preserves `\n` and spaces (only strips tashkeel/ZWNJ, folds
  presentation forms/lam-alef, unifies digits/letters) — that's what makes
  `\n` a safe hard boundary and `" "` a safe word join.
- When verifying RED against an old engine version: `git checkout <old> --
  <engine files>` while OTHER files still reference new struct fields
  (e.g. CLI reading `Match::spans`) breaks the build for the wrong reason,
  and the stale test binary can fool you. Stash ALL dependent changes and
  confirm the target relinked before trusting the result.
- **Stale binary after `git stash`/`stash pop`** (same family as above):
  the already-built binary still contains the PRE-STASH code, so running
  ctest right after `stash pop` gives a false FAIL on the suite you just
  changed. Observed: `UnitTestsSearchText` "failed" in ctest immediately
  after pop because the binary still held the RED code. Always rebuild
  after any working-tree change before trusting test output.
- **Verification scripts must assert every claimed result line and capture
  the failing test's NAME.** A script that prints the ctest summary but
  only gates (grep -q + exit) on the focused suite's totals can print
  VERIFY-OK on a 92% run. Gate each claimed line, run `ctest
  --output-on-failure` and record the failing test name; when a flake
  appears, re-run to characterize it and reproduce with the change
  stashed to prove it pre-exists. (Observed: intermittent
  `UnitTestsPageOps::deletePageMultiplePages` sha256 mismatch — a
  pre-existing `delete-page` determinism flake, unrelated to search
  changes; it passed on the majority of runs both with and without the
  search change.)
- CI format gate: upstream-derived files whose only diff is line-ending
  normalization (CRLF→LF from a rename) fail clang-format; add them to the
  AUTHORED_FILES exclusion list in `ci/run-ci.sh` rather than reformatting
  (fork hygiene — never reformat vendored upstream files).
- **CORRECTED (P6): albdf `render` "oversized blob" was NOT a renderer
  artifact — it was the wrong glyph from an invalid CIDToGIDMap.** The
  "14px letterform blob" (and blank single-glyph renders) came from
  Ghostscript/PDF4QT falling back to Identity when the emitter's SHORT
  CIDToGIDMap array was rejected (spec §9.7.4.3 wants 65536 entries or a
  stream). The RealText path (`performTextCharacterDrawing`) EXISTS but is
  NOT in `getDefaultFeatures()` (default = Antialiasing | TextAntialiasing |
  ClipToCropBox | DisplayAnnotations) — so for the CLI render it never ran
  and was a red herring. Verify glyph identity by rasterized SHAPE + the
  CIDToGIDMap, never assume the renderer is wrong first: an "oversized
  blob" where a small mark should be is the classic signature of Identity
  fallback painting Latin 'A' (gid 2). Full evidence:
  `references/p6-cidtogidmap-spec-compliance.md`.
- **Differential-probe caveat: the probe is immune to layout quirks ONLY if
  the two PDFs differ in nothing but the feature glyph.** The Ts emission
  necessarily changes the TJ structure (`[<a>] TJ rise Ts <m> Tj 0 Ts
  [<b>] TJ` vs one `[<a m b>] TJ`), which makes the RealText renderer
  re-lay-out the base glyphs — so the diff mask then contains base-glyph
  shifts, NOT just the feature's ink. When a fix must alter stream
  structure, verify the base glyphs are pixel-identical first (best-fit
  correlation of the base-letter regions) before trusting diff-band
  assertions; or compare against a control that changes structure without
  the feature.
- **Single-glyph pages used to render BLANK — that was the P6 CIDToGIDMap
  bug, not a renderer quirk.** With the invalid short array ignored
  (Identity fallback), code 1 = GID 1 = `.null` = invisible. Since the
  65536-entry stream fix (commit 74a1166), single "ا" renders a real 2×16px
  stroke in BOTH Ghostscript and albdf render — the ≥2-glyph workaround is
  no longer needed.
- Pixel-probe tests for glyph-position symptoms (marks, offsets) should use
  a **differential probe**: render base text vs base+feature (byte-identical
  PDFs except the feature glyph), diff the PNGs, and assert on the diff mask
  relative to the base ink band — this is immune to the renderer's layout
  quirks (base glyphs paint identically; the diff isolates the feature's
  ink). Calibration recipe + verified numbers:
  `references/p3-render-probe-calibration.md`.
- **Verify glyph identity by rasterized SHAPE, never by unicode/extents
  assumptions.** In Vazirmatn, gid 1173 is the ALEF (tall thin stroke) and
  gid 1266 is the MEEM (wide ring) — uharfbuzz extents alone mislead (alef
  reads 6px wide, meem 13px). Also, CIDToGIDMap (what actually paints) and
  ToUnicode (logical char) can DISAGREE in albdf PDFs (per-instance codes):
  read painted identity from CIDToGIDMap + shape, never from ToUnicode.
  FreeType bitmap-dump probe recipe: `references/p3-phase2-investigation.md`.

- **Upstream PDF4QT headers are CRLF; edit them byte-exact.** The patch
  tool and read_file render CRLF as LF, so a naive patch can normalize the
  whole file (huge diff + clang-format noise on the format gate). For
  upstream files like `pdftoolabstractapplication.h` do byte-level
  replacements in Python preserving `\r\n`, then confirm with
  `grep -c $'\r' <file>` that the count is unchanged.
- **CLI `enum Option` overflowed Qt 6.8's 32-bit `QFlags` — FIXED
  (2026-08-06, commits `37563db` on the M10 branch / `4bb644f` on main):**
  `src/PdfTool/pdftoolabstractapplication.h` has
  34 option groups; `MovePage = 0x100000000` / `DeletePage = 0x200000000`
  (page-ops commit 4402b1c) widen the enum's underlying type to 64 bits →
  `qflags.h: static_assert failed: QFlags uses an int as storage, so an enum
  with underlying long long will overflow` on Qt ≤ 6.8 (system Qt 6.8.2 AND
  CI, which pins Qt 6.8.*). Qt ≥ 6.9 supports 64-bit QFlags, but the project
  floor is Qt 6.8, so the fix is a minimal 64-bit drop-in `Options` class
  (all usages are `testFlag()` + `Option | Option` + `|/&/~`; keep all 34
  values). The tree builds and ctest is green with this fix in place. Upstream check (sparse shallow
  clone of PDF4QT master): upstream's enum ends at `Redact = 0x02000000`,
  never exceeded 32 bits — the fork's own tool additions caused this, so
  there is no upstream fix to mirror. General class-level lesson + diagnosis
  recipe: `qt-cmake-vcpkg-build` skill, pitfall 10. Also: the main
  checkout's
  `build/bin/albdf` PREDATES 4402b1c, so "already compiled" claims about
  post-page-ops features were never true on this toolchain — compare
  `ls -la build/bin/albdf` with `git log --format=%ci` of the feature commit
  before trusting them.

## References

- `references/m10-fuzz-harness.md` — CLI fuzz harness (DB #30): architecture
  (seeded mutation manifest via `random.Random`, manifest.tsv, exit-code
  classification table, work-dir-relative summary paths for the determinism
  gate), verification recipes (fake SEGV/hang/benign binaries, two-work-dir
  determinism diff), F#1/F#2 evidence (exact stderr for the render
  `std::out_of_range` abort, DPI-hang bisect), CI job, extension guide.
- `references/m10-redact-verification.md` — redact engine walkthrough
  (annotation-only regions, `parseQuadrilaterals` /Rect fallback, glyph-path
  subtraction, QPdfWriter vector-baking inference), Redact-annotation fixture
  recipe via `pdfgen.py`, the QFlags 32-bit overflow root cause + 64-bit
  drop-in fix design, and verification status at session end.
- `references/m10-redact-test-suite.md` — LANDED redact integration suite
  (DB #29, commit 3a7568b): fixture geometry + PDF→image coordinate math,
  scanline black-fraction sampling (bar ≥0.95, text 0.05-0.60, ±0.03
  preservation), input-sanity guard, five test slots, exit-code facts (7/4),
  and the QTemporaryDir-lifetime + fetch-text-empty pitfalls.
- `references/s1-cross-line-search.md` — S#1 cross-LINE search (M10 wave-2,
  DB #28): why the plan's RED geometry is unsatisfiable for RTL (per-line
  visual joins don't compose with whole-query inversion), the verified
  mirror-geometry RED test (`65beb7d`), the LANDED soft-line-boundary GREEN
  (commit `0cf3338`, 2026-08-06: vertical-gap rule `<= 0.5 × max line
  height`, x-overlap guard rejected, uncovered large-gap branch note), and
  host facts (vcpkg path, stale main build dir, active pre-commit hook in
  worktrees via core.hooksPath).
- `references/s1-cross-item-search.md` — S#1 root cause, invalid-test
  geometry saga, searchFlow seam design, evidence commands.
- `references/p3-vertical-mark-offsets.md` — P3 plan: exact code locations,
  Ts emission design, TDD steps, risks.
- `references/p3-render-probe-calibration.md` — P3 Phase-1 RED calibration:
  GPOS y_offsets for fatha/kasra, glyph extents, renderer-quirk evidence,
  verified band numbers, differential-probe + uharfbuzz recipe.
- `references/p6-cidtogidmap-spec-compliance.md` — P6 VERIFIED root cause:
  short CIDToGIDMap array → Identity fallback → Latin-'A' blobs / blank
  single-glyph pages in every strict renderer; spec §9.7.4.3; fix (65536-entry
  stream) + hand-patch proof; Ghostscript-vs-albdf debugging recipe.
- `references/p3-phase2-investigation.md` — P3 Phase-2 GREEN attempt state:
  PDF4QT drawText/Ts source facts (rise unscaled ⇒ H1 formula), the
  RESOLVED renderer root cause (RealText `performTextCharacterDrawing`
  paints QPainter::drawText, not glyph paths), emitted Ts content streams,
  H1 empirical diff numbers (a green / b+c red), TJ-split base-glyph shift
  evidence, gid→shape identity table, CIDToGIDMap-vs-ToUnicode trap, probe
  recipes.
- `references/p3-ts-emission-complete.md` — P3 LANDED state (2026-08-05):
  final emitter form with inkAboveOrigin sign rule, fatha/kasra/sukun
  table, the phantom-space regression (A/B/C isolation proof + zero-advance
  flow guard fix 9a4587d), kasra band recalibration (4ed7ab2), verification
  recipe.
- `scripts/uharfbuzz_gpos_probe.py` — shape Arabic/Hebrew with HarfBuzz and
  print per-glyph advances, GPOS x/y offsets, clusters, extents
  (engine-equivalent buffer setup; run with SYSTEM python3, not the
  execute_code sandbox interpreter).
- `references/p6-cidtogidmap-fix.md` — the LANDED fix (commit 74a1166):
  65536-entry Flate stream emission, exact emitted bytes, GS+albdf pixel
  probes, P3 re-derivation consequence, end-to-end verification recipe.
- `scripts/cidtogidmap_probe.py` — verify an albdf PDF's CIDToGIDMap stream
  (Flate, 131072B, expected code→gid entries) and PNG ink bboxes.
- `references/gui-architecture.md` — GUI-layer design thinking (user asked
  "how will the GUI utilize this binary"): binary-mode (CLI-as-API) vs
  library-mode decision framework, the `--json` output gap (G1), viewer/edit
  milestones G1–G4, self-critique table, and the testing-temp user-corpus
  convention (user PDFs → `/home/agent/workspace/testing-temp/`, NOT repo
  fixtures). Full note: `docs/research/004-gui-architecture.md`.
- `references/gui-text-paths-audit.md` — GUI text search/select/copy/extract
  RTL-reachability audit (2026-08-07, commit 9f5e1338): all 6 paths with
  file:line + widget + mechanism (a-e) + RTL-benefited verdict; GUI search
  bypasses the engine (plain `indexOf`), GUI copy gets `/ActualText` repair
  for free, OCR bypasses it; minimal `Match→PDFFindResult` adapter wiring
  (keeps the GUI's `PDFFindResults` shape), P0/P1/P2 fix list, corrected
  file locations (`pdfdocumenttextfloweditormodel.h` lives in
  `Pdf4QtLibCore/sources/`, not `PdfDocument/`).
- **GUI text input does NOT go through the RTL engine (2026-08-07 audit).**
  Before claiming "RTL is wired into the GUI", know: every GUI text-input path
  (form fields, FreeText, canvas textbox, content-editor text items) commits via
  raw QLineEdit/QTextEdit/QPainter::drawText — the engine's `PDFRTLTextEngine`
  is CLI-only (`add-text --rtl`). The single integration choke point is
  `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
  (pdfdocumentbuilder.cpp:1489-1575) → `annotation->draw()` → PDFContentStreamBuilder:
  one RTL branch there fixes form-field AND FreeText appearance streams while
  `/V`/`/Contents` stay logical. Full file:line map + P0/P1/P2 list:
  `albdf-fork-development` skill → `references/gui-text-input-rtl-audit.md`.
- **GUI find does NOT use `PDFTextSearchEngine` (verified 2026-08-07).** Both GUI
  find entry points — `PDFAdvancedFindWidget::performSearch`
  (pdfadvancedfindwidget.cpp:292,312) and `PDFFindTextTool::performSearch`
  (pdfwidgettool.cpp:610,622) — call the legacy `PDFTextLayoutStorage::find` →
  `PDFTextFlow::find` = plain `m_text.indexOf` (pdftextlayout.cpp:1353): no FriBidi
  inversion, no normalization, no cross-line. Wiring RTL search into the GUI means
  calling `PDFTextSearchEngine::search` and mapping `Match` → `PDFFindResult`
  (core-defined, pdftextlayout.h:304-318) — simplest bridge:
  `PDFTextLayout::createTextSelection(pageIndex, boundingRect corners)`
  (h:449-453) feeds the existing highlight/copy pipeline unchanged. Also: CLI RTL
  add-text bypasses `PDFPageContentEditorProcessor` (fresh stream + font merge,
  pdftooladdtext.cpp:200-537) — mirror that for GUI RTL insert; and R#4 (content
  rewrite drops `/ActualText` BDC/EMC) has a full fix design. Everything:
  `albdf-fork-development` skill → `references/gui-text-wiring-audit-2026-08-07.md`.

**M14 FreeText AP RTL branch (design verified 2026-08-08, NOT yet implemented).** The
`PDFFreeTextAnnotation::draw` QPainter path (pdfannotation.cpp:2713, backed by QPdfWriter via
`PDFContentStreamBuilder`) is structurally hostile to font embedding — a QPainter cannot inject a
Type0/FontFile2 dict into the AP `/Resources`. The RTL branch must live in
`PDFDocumentBuilder::updateAnnotationAppearanceStreams` (pdfdocumentbuilder.cpp:1489) as a strictly
additive early-return mirroring the existing `updateHighlightAnnotationAppearanceStream` pattern
(:1652-1794): `PDFRTLTextEngine::create` → `replaceObjectsByReferences(fontDictionary)` (:1095) →
form XObject `<< /Type /XObject /Subtype /Form /BBox ... >>` → `mergeTo(annotationReference, /AP)`
(:1792). `/Contents` stays logical; LTR falls through untouched. Full verified file:line map, GREEN
design, RED core-level test recipe (PDFDocumentModifier → `createAnnotationFreeText(...,"سلام",...)`
→ walk `/AP /N /Resources /Font` for `/Subtype /Type0` + `/FontFile2`; baseline fails — QPdfWriter
emits only base-14 Helvetica, no FontFile2), baseline facts (16/16 ctest green, no PROBLEMS.md
FreeText entry yet) and continuation steps: `references/m14-freetext-ap-design.md`.

**M14 form-field AP — the headless path is a NO-OP, not just tofu (verified 2026-08-08, WS-A
recon, fix in flight).** `albdf form-fill form.pdf out.pdf --field name --value 'سلام'` exits 0 but
the output has `/V` and **NO `/AP`, NO `/FontFile2`, NO `/Type0`** — the headless field is invisible
to viewers (stronger red than tofu: there is no appearance at all). Root cause:
`PDFFormManager::drawFormField` (pdfform.cpp:914) is a `Q_UNUSED` **no-op in core**; real drawing
only exists in the optional GUI's `PDFWidgetFormManager`. `PDFWidgetAnnotation::draw`
(pdfannotation.cpp:3249) calls it; `PDFFormFieldText::setValue` (pdfform.cpp:983) triggers
`builder->setFormFieldValue` + `updateAnnotationAppearanceStreams(widget)` — so the choke point is
the same `updateAnnotationAppearanceStreams` (:1489). **Font-source decision (orchestrator):** core
`fonts.qrc` bundles only Liberation (Latin); do NOT vendor an Arabic font into core resources —
instead add a `--font <ttf>` option to the `form-fill` CLI mirroring `add-text --font`
(pdftooladdtext.cpp:183-188 pattern: read TTF bytes, pass into the builder/form manager so the AP
generator can embed), and let the RED test pass `TEST_FONT_ARABIC` through the CLI. The RTL branch
reads the field `/V` via `formManager->getFormFieldForWidget()` (pdftoolformfill.cpp already wires
`PDFFormManager`), uses `PDFAnnotationDefaultAppearance::parse(getDefaultAppearance())` for
fontSize/family, x/y from `annotation->getRectangle()` with quadding. RED asserts the output PDF
contains `/AP` + `/FontFile2` (or `/Type0`). LTR behavior stays minimal (only RTL values get the
engine AP branch, or note the no-AP-at-all state as its own bug). **WS-B refinement (2026-08-08):
the no-AP state has TWO stacked causes** — (1) the drawFormField no-op AND (2) the CLI never calls
`modifier.getBuilder()->setFormManager(&formManager)` (pdftoolformfill.cpp:147-148), so
`PDFWidgetAnnotation::draw` bails at pdfannotation.cpp:3252 on the null `parameters.formManager`
before even reaching the no-op. The RTL AP branch must therefore read the field dict from the
builder's storage (widget `/V` or `/Parent` walk), NOT from `m_formManager`. Full verified
file:line implementation map (call chain, engine template, builder APIs, CLI plumbing, test
wiring, session state): `references/m14-form-field-ap-impl-map.md`. Original recon incl. the
empirical 1694-byte baseline probe: `references/m14-form-field-ap-recon.md`.

**R#4 LANDED (2026-08-07, commits 1d7b8c69 RED + 80548d8c GREEN).** The content
editor now preserves `/ActualText` marked content on re-edit:
`PDFPageContentEditorProcessor` overrides `performMarkedContentBegin(const QByteArray&,
const PDFObject&)` / `performMarkedContentEnd()`, resolves `/ActualText` as a string
(same guard as pdftextlayoutgenerator.cpp:91-101, decodes via
`PDFEncoding::convertTextString`), and appends an `Item` carrying
`QByteArray actualText` (UTF-16BE+BOM, the engine's byte format) to the current text
element's item list — nesting-safe via `std::vector<QByteArray> m_actualTextStack`,
outermost-only recorded, NO 4th element Type (audit-rejected). The builder
(`PDFPageContentEditorContentStreamBuilder::writeText` / `writeTextCommand`) re-emits
`/Span << /ActualText <FEFF...> >> BDC` before the item's BT/Tf/Tm section and `EMC`
after it, tracked by `m_isActualTextSpanOpen`. Result: a second LTR add-text on an RTL
page keeps the full lam-alef (`ملاس`) — the mixed-case test expectation was updated
from the degraded `ملس` (which PINNED the old bug) to the full ligature (`e7c1a8eb`).
Both touched files were already format-gate-exempt (upstream-derived).

**RTL clipboard re-inversion LANDED (2026-08-07, a8b2a7c0 core + b48bcd40 GUI).**
`PDFRTLTextNormalizer::invertToLogical(const QString& visual)` (public static) applies
the FriBidi vis2log step — fribidi_vis2log does NOT exist in vendored FriBidi 1.0.16
(removed in 1.0; only a TODO ref remains), so it is EMULATED: `fribidi_get_bidi_types`
→ `fribidi_get_par_embedding_levels_ex` (base `FRIBIDI_PAR_ON`, mirroring the engine's
invertToVisual) → `fribidi_reorder_line` over the VISUAL string. **Trap:
`fribidi_reorder_line`'s `map` parameter is INPUT+OUTPUT — initialize it to identity
first, else it returns success with an untouched map (garbage).** Round-trip verified:
`مالس`→`سلام`, `123 مالس`→`سلام 123`, `abc مالس def`→`abc سلام def`, `םולש`→`שלום`,
LTR passthrough. GUI: `PDFSelectTextTool::onActionCopyText` (pdfwidgettool.cpp:867)
re-inverts when `text.isRightToLeft()` before `QApplication::clipboard()->setText`;
LTR untouched; CLI `fetch-text` contract (visual order) UNCHANGED. Table-extract
copy path NOT inverted (mixed LTR digits + RTL in one cell makes per-cell vis2log
wrong — not trivially safe). Full emulation + tests:
`references/fribidi-vis2log-emulation.md`.
