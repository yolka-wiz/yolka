# Qt 6.8/6.9 public APIs for shaped RTL text → PDF Type0 embedding

Verified 2026-08-08 against: system Qt 6.8.2 headers (Debian `qt6-base-dev
6.8.2+dfsg-9+deb13u2`, `/usr/include/x86_64-linux-gnu/qt6/QtGui/`), official
docs (doc.qt.io/qt-6), and Qt 6.8 source (`qtbase/src/gui/text/qtextlayout.cpp`,
`qtextengine.cpp`, `qfontengine.cpp`). Qt 6.9 adds nothing material to these
classes.

## Verdict

**Feasible with public APIs — with caveats.** All four data streams needed for
a Type0 font (visual-order glyph indices, advances, cluster mapping, RTL
direction) are obtainable via `QTextLayout`/`QTextLine::glyphRuns()` with
`RetrieveAll` flags — no private Qt headers, and no explicit harfbuzz/fribidi
deps (see runtime facts). The work sits in the PDF layer: deriving advances
from positions, reconstructing ligature char-spans for the ToUnicode CMap,
embedding the full font via `QRawFont`, and deciding how to handle diacritic
y-offsets (baseline-flatten vs. Ts-split — albdf's P3 solution applies).

## Pipeline recipe (all public API)

```cpp
QTextLayout layout(text, font);            // or setRawFont(QRawFont)
QTextOption opt; opt.setFlags(QTextOption::IncludeTrailingSpaces);
layout.setTextOption(opt);                 // 0x80000000: keep trailing-space width
layout.beginLayout();
QTextLine line = layout.createLine();
line.setLineWidth(width);                  // or setNumColumns for RTL-justified
layout.endLayout();
// MUST use QTextLine::glyphRuns, NOT QTextLayout::glyphRuns (see pitfalls)
const auto runs = line.glyphRuns(-1, -1,
    QTextLayout::RetrieveGlyphIndexes | QTextLayout::RetrieveGlyphPositions
    | QTextLayout::RetrieveStringIndexes | QTextLayout::RetrieveString);
for (const QGlyphRun &run : runs) {
    QList<quint32>  gids      = run.glyphIndexes();   // visual order, per run
    QList<QPointF>   pos       = run.positions();     // x AND y (GPOS marks!)
    QList<qsizetype> strIdx    = run.stringIndexes(); // per-glyph first-char idx
    QString          src       = run.sourceString();
    bool             isRtl     = run.isRightToLeft(); // or flags() & RightToLeft
    QRawFont         font      = run.rawFont();       // the actual engine font
    // advance[i] = pos[i+1].x - pos[i].x  (last glyph: use line width)
}
```

## Capability checklist (exact names, verified in 6.8.2 headers)

| Need | API | Notes |
|---|---|---|
| Glyph indices, visual order | `QTextLine::glyphRuns(from, length, QTextLayout::GlyphRunRetrievalFlags)` → `QGlyphRun::glyphIndexes()` (`QList<quint32>`) | Runs come back in **visual order** per line — but ⚠️ **WITHIN an RTL run glyphs are in LOGICAL order with descending x** (probe-verified 2026-08-08, Noto Naskh Arabic on 6.8.2: س,ل,ا,م at x 17.6,12.6,7.8,0). PDF emission (leftmost-first) needs a per-run reversal or x-sort. Qt reverses the HB buffer back to logical; only the ITEMS (runs) are reordered visually |
| Advances | derived from `QGlyphRun::positions()` deltas | No advance accessor on QGlyphRun. `QRawFont::advancesForGlyphIndexes(..., KernedAdvances)` only applies the KERN table, **not GPOS** — use position deltas |
| Cluster mapping | `QGlyphRun::stringIndexes()` (since 6.5) + `sourceString()` (since 6.5) | Per-glyph first source-char of cluster. Gaps = ligature (1 glyph → N chars); duplicates = decomposition (1 char → N glyphs). Requires `RetrieveStringIndexes` flag. ⚠️ **PROBE-GOTCHA (2026-08-08): plain `line.glyphRuns()` (default flags) returns stringIndexes() EMPTY** — the RetrieveStringIndexes path itself is NOT yet probe-verified; run `scripts/qt_rtl_probe.cpp` before betting a port on it |
| Visual order guarantee | `QTextLine::glyphRuns` walks `QTextLineItemIterator`, whose `next()` does `item = visualOrder[logicalItem] + firstItem` (qtextengine.cpp:3858) | Ordering is per LINE |
| Mark/GPOS attachment | `QGlyphRun::positions()` includes y-offsets (qfontengine.cpp:295-296: `gpos_y = ypos + glyphs.offsets[i].y`) | **`QTextLine` has NO `verticalAdvance`** — zero occurrences in all public QtGui headers; it's an internal QTextEngine concept. PDF `TJ` is horizontal-only → marks need `Ts` (albdf P3 solution) or baseline-flatten |
| Logical↔visual map | none public | Reconstruct: iterate `QTextLine::glyphRuns()` (visual), `stringIndexes()[i]` = logical char of visual glyph i. Bidi-aware cursors are public: `QTextLine::cursorToX/xToCursor`, `QTextLayout::leftCursorPosition/rightCursorPosition` |
| Font bytes for FontFile2 | `QRawFont::loadFromData(const QByteArray&, qreal, HintingPreference)` / `loadFromFile()` (TTF/OTF only); `QRawFont::fontTable(QFont::Tag|const char*)` (since 6.7) → raw big-endian sfnt tables | Qt does **not** subset — embed full font or write your own subsetter |
| FontDescriptor metrics | `unitsPerEm()`, `ascent()`, `descent()`, `capHeight()`, `lineThickness()`, `underlinePosition()`, `setPixelSize()`, `fromFont(QFont, WritingSystem)` | |
| QTextOption flags | `IncludeTrailingSpaces` (0x80000000), `ShowLineAndParagraphSeparators`, `ShowTabsAndSpaces`, `AddSpaceForLineAndParagraphSeparators`, `SuppressColors`, `ShowDocumentTerminator` | ⚠️ **`SuppressHyphenation` does NOT exist in Qt 6** (Qt 5 flag, removed). Irrelevant for Arabic |

## Pitfalls

1. **Never use `QTextLayout::glyphRuns()` for ordering** — it merges runs into a
   `QHash<(fontEngine, flags), QGlyphRun>` and returns `glyphRunHash.values()`
   (qtextlayout.cpp:1043-1079); hash iteration order is unspecified across
   fonts/flags. Always go through `QTextLine::glyphRuns()` per line.
2. **`QRawFont::glyphIndexesForString()` is a raw CMAP lookup, NOT shaped** (doc:
   "Converts a string of unicode points to glyph indexes using the CMAP table").
   It will NOT produce Arabic joining/ligature forms. Correct division of labor:
   QTextLayout for shaping, QRawFont for metrics/tables.
3. **Cluster span reconstruction is direction-aware**: within an RTL run,
   `stringIndexes()` decreases along visual order. To find a ligature's full
   char range for ToUnicode (CID → multiple U+ values), use the adjacent
   glyph's string index — direction matters.
4. **`setRawFont(QRawFont)` + `QGlyphRun::rawFont()`** let you drive the whole
   pipeline from a specific loaded font (e.g. the exact TTF you'll embed) —
   avoids font-fallback surprises (multi-engine runs split into several
   QGlyphRun objects, one per QFontEngine).

## Runtime facts (Linux, verified via ldd + source)

- **HarfBuzz is already inside QtGui.** `ldd /usr/lib/x86_64-linux-gnu/libQt6Gui.so.6`
  → `libharfbuzz.so.0`. `QTextEngine::shapeTextWithHarfbuzzNG()`
  (qtextengine.cpp:1598) calls `hb_shape_full()` with shaper list
  `{"graphite2","ot","fallback"}`, sets `HB_DIRECTION_RTL/LTR` from the bidi
  level, reverses RTL buffers. So "no explicit HB dep" costs nothing at
  runtime — your app links only `Qt6::Gui`. Non-HB fallback exists in
  `shapeText()` (`!shapingEnabled` → `stringToCMap`) but does NOT do Arabic
  joining/ligatures and only triggers with `QFont::PreferNoShaping` or
  HB compiled out (`QT_CONFIG(harfbuzz)` — never in distro builds).
- **Bidi is Qt's own UAX #9 implementation, no fribidi.** Private
  `QBidiAlgorithm` struct in qtextengine.cpp (handles isolates LRI/RLI/FSI,
  mirroring via `QUnicodeTables::properties()`); `QTextEngine::bidiReorder()`
  produces the per-line visual-order array. No public bidi API exists.

## How to verify Qt API facts fast (repeatable research workflow)

1. Local headers: Debian ships them at `/usr/include/x86_64-linux-gnu/qt6/QtGui/`
   (package `qt6-base-dev`); check version via `dpkg -l | grep qt6-base`.
2. Official docs: `curl -sL https://doc.qt.io/qt-6/<class>.html` then strip
   tags with a python regex (web_extract may be unavailable; curl works).
3. Source: codebrowser.dev 403s; use code.qt.io cgit plain-text URLs:
   `curl -sL -A "Mozilla/5.0" "https://code.qt.io/cgit/qt/qtbase.git/plain/src/gui/text/qtextlayout.cpp?h=6.8"`
   (also qtextengine.cpp, qfontengine.cpp, qtextengine_p.h).
4. Linkage facts: `ldd libQt6Gui.so.6 | grep -iE "harfbuzz|fribidi|freetype"`.

## Empirical probe addendum (2026-08-08) — `scripts/qt_rtl_probe.cpp`

Runnable probe (system Qt 6.8.2, Noto Naskh Arabic from the repo's
`src/tests/fonts/`) that CROSS-CHECKS the source-based claims above. Results:

- **Shaping parity: QTextLayout == direct hb_shape.** Same GIDs: `سلام` →
  35,69,11,72 (joined forms; unshaped QRawFont cmap = 32,66,8,72), `مَا` →
  77,380,9 (meem/fatha/alef). If a port keeps hb only for clusters, GIDs will
  agree.
- **/W parity: `QRawFont::advancesForGlyphIndexes(gids, SeparateAdvances)` ==
  `hb_font_get_glyph_h_advance` byte-for-byte** (gid 77: 455.7u vs HB 456u;
  mark: 0). The `/W` array survives a Qt port unchanged. (The reference's
  "advances from position deltas" advice is for SHAPED layout advances; the
  hmtx /W source is QRawFont.)
- **GPOS mark offsets ARE in positions()**: fatha glyph y=20.25 vs constant
  base baseline y=17.1094 px @12px/1000upem → y-offset publicly retrievable
  for the albdf Ts mechanism. ⚠️ Value ≈262u, HB raw `y_offset` = −196u —
  Qt adds the pen advance; sign AND magnitude differ → recalibrate
  `test_verticalMarkOffsets` band if porting.
- **Mark ink direction**: `QRawFont::boundingRect(gid)` public ink bbox
  (fatha gid 380 → (0,-11 3x3), ink above origin) replaces
  `hb_font_get_glyph_extents` for the `inkAboveOrigin` Ts sign rule.
- **stringIndexes() EMPTY with default `line.glyphRuns()`** (no Retrieve*
  flags) — do not assume cluster data without the flags; open question
  whether RetrieveStringIndexes fills it (see checklist row).
- **Run geometry**: RTL run glyphs in LOGICAL order, descending x; runs
  across a line visual (LTR, RTL, space, LTR at ascending x). Line width
  from Qt (12.33px for مَا) ≠ Σhmtx (8.5px) — decide deliberately which
  drives run width.
- **No public string-level bidi reorder** (invertToVisual / invertToLogical
  for search need a hand-written UAX#9 or keep FriBidi) and **no public way
  to force script/language** (Urdu variants etc. — auto-detect only).
- Probe pitfalls: QGuiApplication (offscreen) REQUIRED before
  QFontDatabase::addApplicationFontFromData (segfault without); g++
  link via `pkg-config --cflags --libs Qt6Gui Qt6Core`; set QRawFont
  pixelSize = unitsPerEm() for 1 unit = 1 font unit; uharfbuzz ground truth
  needs SYSTEM python3, not the execute_code sandbox venv.
- Font-fallback risk: `QFont(family)` silently falls back to a system font
  if the family isn't registered → wrong GIDs corrupt the Type0 font; verify
  `run.rawFont()` identity/family after shaping.
