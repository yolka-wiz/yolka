# P6 — CIDToGIDMap short array → 65536-entry Flate stream (fixed 2026-08-05)

## Root cause (verified with Ghostscript before the fix)

- `pdfrtltextengine.cpp` emitted `/CIDToGIDMap [0 681]` (one entry per used
  glyph). PDF 32000-1 §9.7.4.3 requires **65536 entries** for a 2-byte-CID
  font, or a **stream**.
- Both strict renderers ignore the short array and fall back to /Identity:
  - Ghostscript (spec-strict)
  - PDF4QT's own parser — `pdffont.cpp` ~line 2352 reads the map ONLY when
    the object `isStream()`
- Consequences, all verified: code 1 = GID 1 = `.null` (invisible), code 2 =
  GID 2 = Latin 'A'. **EVERY RTL output painted wrong glyphs in every
  renderer.** Single "ا" rendered NO INK; "مَا" rendered as 'A' shapes.
- The earlier Phase-2 P3 "14px mark blob" was literally 'A', not the fatha.
- Proof: hand-patching alef.pdf with a proper stream made Ghostscript paint
  the alef (2×16px stroke).

## The fix (commit 74a1166, "fix(rtl): emit spec-valid 65536-entry CIDToGIDMap stream (P6)")

Replaced the array with an indirect **FlateDecode stream**:

- 65536 × 2-byte BIG-ENDIAN entries: entry[0] = 0 (.notdef), entry[code] =
  gid from `codeToGid` (per-instance codes start at 1 → code = index+1), all
  other entries 0. Raw 131072 bytes.
- Compressed with `PDFFlateDecodeFilter::compress` (already used for
  FontFile2 in the same function). Dict: `<< /Length N /Filter /FlateDecode
  >>`, emitted via `PDFObject::createStream(std::make_shared<PDFStream>(...))`
  — the FontFile2 pattern, NOT the uncompressed ToUnicode pattern.
- Loop guard: `code + 1 <= 65535` (content stream emits 2-byte codes; guards
  against a >65535-glyph input writing out of bounds).

## Verified emission (real emitter, vazirmatn-Regular)

| PDF | stream object | raw | decoded | nonzero entries |
|---|---|---|---|---|
| "ا" | 5 `<< /Length 152 /Filter /FlateDecode >>` | 152B | 131072B | {1: 681} |
| "مَا" | 5 `<< /Length 159 /Filter /FlateDecode >>` | 159B | 131072B | {1: 1173, 2: 728, 3: 1266} |

(1173 = meem, 728 = fatha, 1266 = alef in Vazirmatn — same values the old
array carried; only the container changed to spec-valid.)

## Renderer pixel probes (72 dpi, PIL ink bbox, threshold <64)

| probe | bbox | ink px | verdict |
|---|---|---|---|
| Ghostscript "ا" | 2×16 | 32 | real alef vertical stroke — not blank, not 'A' |
| Ghostscript "مَا" | 16×17 | 93 | alef column + meem ring + fatha tick |
| albdf render "ا" | 2×16 | 32 | matches Ghostscript |
| albdf render "مَا" | 16×16 | 76 | same structure (RealText mark-blob quirk remains) |

ASCII shape proof: alef = full-height `##` column; مَا = left 2px alef column
+ right meem ring + top fatha tick. A Latin 'A' would be a ~15×17 triangular
mass with no full-height left column — that column is the 'A'-discriminator
(an 'A' inks its left column only in the bottom rows).

## Consequence for P3 (Phase 2b)

Re-derive kasra sign and the rise formula with CORRECT glyphs — the earlier
±3.93 "kasra drop" measured 'A'. Ghostscript now paints real glyphs, so
Ghostscript-based calibration is meaningful again.

## Reusable verification recipe

1. Emit PDFs: `QT_QPA_PLATFORM=offscreen build/bin/albdf add-text
   src/tests/fixtures/blank.pdf out.pdf --page 1 --x 72 --y 700 --text "ا"
   --size 24 --rtl --lang fa --font src/tests/fonts/Vazirmatn-Regular.ttf`
2. Inspect stream: regex `/CIDToGIDMap\s+(\d+)\s+0\s+R` → find `<N> 0 obj` →
   `stream\r?\n ... endstream` → `zlib.decompress` → assert 131072 bytes →
   dump nonzero entries (see `scripts/cidtogidmap_probe.py`).
3. Ghostscript: `gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r72
   -sOutputFile=x.png out.pdf` → PIL ink bbox + ASCII-art rows for shape
   identity.
4. albdf render: `mkdir -p` the output dir FIRST (render does not create
   it), separate dir per PDF (Image_1.png overwrites).
5. ctest baseline at this phase: 10/11 pass + 1 expected RED fail
   (`UnitTestsRtlAddText::test_verticalMarkOffsets`, Ts/Phase 2b).
