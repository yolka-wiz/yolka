# P3 Phase-2 investigation (GREEN attempt — renderer facts & results)

State at handoff (2026-08-05): RED test committed at `dc3e1d8`. A later
session implemented the H1 Ts emitter in `pdfrtltextengine.cpp` (working
tree, NOT committed): H1 greens assertion (a) only; (b)+(c) stay RED and
are unsatisfiable from the emitter side while the RealText renderer paints
mark blobs (root cause below). Next agent resumes here — do not re-derive
these facts.

## Verified source facts: how PDF4QT applies Ts (pdfpagecontentprocessor.cpp)

Read directly from source (~lines 3218–3410):

- `drawText()` builds `adjustMatrix(horizontalScaling * fontFactor, 0.0, 0.0,
  fontFactor, 0.0, textRise)` then `textRenderingMatrix = adjustMatrix *
  textMatrix` and maps the glyph path through it (`textRenderingMatrix.map(
  glyphPath)`).
- ⇒ `textRise` (the `Ts` value) enters the matrix **unscaled by fontSize**.
  The font-size scale lives in the pre-scaled glyph path; `Tm` carries no
  scale (`operatorTextSetMatrix` sets the text matrix directly).
- TJ numeric items move the pen by `-item.advance * 0.001 * fontSize *
  horizontalScaling` — the `/W` array is in 1000-unit-per-em space
  (Vazirmatn alef advance 536 units → `/W 262` = 536*1000/2048).

**Consequence:** the emitted `Ts` should be the point displacement directly,
`rise = yOffset * fontSize / upem` (design's H1; fatha −146 @24pt/2048 →
1.71pt). H2 (`rise = yOffset/upem` = 0.07pt) cannot clear the base top.
Source strongly favors H1 — still confirm empirically with the RED test
(the QVERIFY2 messages print observed diff rows `%4..%5`; iterate on those).

## Glyph identity table (Vazirmatn, upem 2048) — verify by SHAPE

Rasterize each gid with FreeType at 24pt and LOOK at the bitmap; extents
alone mislead:

| gid | shape at 24pt | identity |
|---|---|---|
| 1173 | tall thin stroke, slight bottom curve | ALEF |
| 1266 | wide ring, open at bottom | MEEM |
| 728 | small diagonal slash, ink y 1141..1410 units (high in em) | FATHA |
| 731 | small slash, ink y −236..33 units (below origin) | KASRA |

Fatha and kasra BOTH have negative y_off yet must move opposite directions
(fatha up, kasra down): marks are drawn at their final vertical positions in
the font; y_offset is the GPOS attachment translation, not the final
direction. Do not infer direction from the sign of y_offset alone.

## RESOLVED root cause: RealText paints QPainter::drawText, not glyph paths

`PDFPainter::performTextCharacterDrawing` (pdfpainter.cpp ~line 270):
when the `PDFRenderer::RealText` feature is on (default for the CLI
render), EVERY character is painted with
`m_painter->drawText(QPointF(0,0), QString(info.character))` using a QFont
from `getFontForTextDrawing`; the embedded glyph outlines are never
painted (the `handledAsRealText` branch in pdfpagecontentprocessor.cpp
drawText skips `processPathPainting`). This explains ALL the renderer
quirks:

- zero-advance mark → oversized ~14px letterform blob at the pen (the
  rasterized QFont mark, not the 5×3px glyph);
- `ما`/`اا` pixel-identical composites and double-reversal — Qt's
  per-character rasterization, not content-stream painting;
- **each Tj/TJ is a SEPARATE drawText call** (operatorTextShowTextString
  → fillTextSequence → drawText), with textRise read from the graphic
  state at call start. Ts IS honored (adjustMatrix dy) but applies to the
  blob, not the glyph.

## Emitter implementation (H1, verified, NOT committed)

`pdfrtltextengine.cpp` emitter loop: Ts is a text-state operator, so it can
only appear between CLOSED TJ arrays. Working structure (a `flushTj`
lambda emits `[<items>] TJ` to `content` and clears the accumulator):

- per glyph: `xOffset && xAdvance` → flushHex + numeric item (unchanged);
- `yOffset != 0` → flushHex(); flushTj(); then
  `content += "<rise> Ts\n<HEX> Tj\n0 Ts\n"` with
  `rise = -glyph.yOffset * settings.fontSize / metrics.upem` ('f' 2);
- else → append hex to currentHex; after loop flushHex(); flushTj().

Emitted streams (decompressed from real PDFs):

```
مَا:  [<0001>] TJ / 1.71 Ts / <0002> Tj / 0 Ts / [<0003>] TJ   (fatha +1.71)
بِسْم: [<0001>] TJ / -0.16 Ts / <0002> Tj / 0 Ts / [<0003>] TJ / 3.93 Ts
      / <0004> Tj / 0 Ts / [<0005>] TJ   (shadda y_off +14 → −0.16, kasra +3.93)
```

Non-mark runs emit a single TJ, byte-identical to the old emitter;
extraction tests (hebrewRoundTrip, persianExtraction, rtlKeepsLtrIntact,
rtlNotMirrored) all stayed green — multiple TJ arrays in a row do NOT
insert phantom spaces (no Tm/Td boundary).

## H1 empirical result (72dpi pixel probes; base ink rows 74..91)

- Fatha diff band moved 78..91 → **73..91**: above-band [68,73] hit →
  assertion (a) PASSES. But the blob still spans the core band [76,89] →
  (b) FAILS. The blob is ~14px tall; clearing the core band needs a rise
  ≳16pt ≈ 10× the GPOS-correct 1.71pt — impossible without breaking the
  mark's true position. ⇒ **The RED test is NOT satisfiable from the
  emitter side while the RealText renderer paints blobs.** Test's
  "H1 ⇒ rows ~74..77 ⇒ GREEN" calibration assumed the 5×3px glyph; that
  premise is false.
- Kasra probe (بِسْم): diff 70..92, nothing at rows ≥ 94 → (c) FAILS.
- **TJ-split side effect (contaminates the differential diff):** with the
  split stream, the RealText renderer re-laid-out the base glyphs — alef
  shifted up ~2px (outline diff), meem moved +11/−6 (best-fit correlation,
  residual 0). So the diff mask contains base-glyph shifts, not just the
  mark's ink. Differential probes are immune ONLY when the two PDFs differ
  solely in the feature glyph AND the stream structure is unchanged.

## Fix direction (hypothesis, NOT validated)

Neutralize the blob before re-testing: disable `PDFRenderer::RealText` for
probe renders, or fix `performTextCharacterDrawing` to paint the glyph path
at the content-stream position. Then the GPOS-correct H1 emission should
land fatha at rows ~74..77 and kasra below 94 — verify empirically. Kasra
sign: y_off −335 (negative like fatha) but must move DOWN — resolve against
actual pixels after the renderer fix; never infer from the sign of y_offset
alone (marks are drawn at their final vertical position in the font;
y_offset is the GPOS attachment translation).

Empirical rule this proves: never predict mark ink position from
content-stream/TJ math; always iterate against the actual pixel diff.

## Reusable probes

- uharfbuzz GPOS probe: `scripts/uharfbuzz_gpos_probe.py`. Run with the
  SYSTEM python3 (has uharfbuzz 0.56) — the `execute_code` sandbox
  interpreter does NOT have it. uharfbuzz 0.56 API notes:
  `hb.ot_tag_to_script("Arab")` takes str (bytes → TypeError); no
  `hb.Script`/`hb.script_from_string` in this version;
  `font.get_glyph_extents(gid)` → (x_bearing, y_bearing, width, height),
  height negative = ink extends downward.
- PDF stream dump (python): regex `stream`..`endstream`, try raw then
  `zlib.decompress`; the page content stream is FlateDecode'd; the FontFile2
  is a FULL embed (same byte size as the source TTF, gids unchanged), so
  source-font probes are valid. Content-stream glyph order = shaped visual
  order; paint identity comes from `/CIDToGIDMap` + shape — ToUnicode
  (logical) and CIDToGIDMap (painted) can DISAGREE (mark PDF: code1 →
  GID1173 meem-shape while ToUnicode says U+0627).
- FreeType glyph-bitmap probe (C, `gcc ftbmp.c -o ftbmp $(pkg-config
  --cflags --libs freetype2)`):

```c
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char** argv) {          // ftbmp <font.ttf> <gid> [size]
    int size = argc > 3 ? atoi(argv[3]) : 24;
    FT_Library lib; FT_Init_FreeType(&lib);
    FT_Face face; FT_New_Face(lib, argv[1], 0, &face);
    FT_Set_Char_Size(face, 0, size * 64, 72, 72);
    FT_Load_Glyph(face, atoi(argv[2]), FT_LOAD_RENDER | FT_LOAD_NO_HINTING);
    FT_Bitmap* b = &face->glyph->bitmap;
    printf("gid %s @%dpt: %ux%u top=%d left=%d\n", argv[2], size,
           b->width, b->rows, face->glyph->bitmap_top, face->glyph->bitmap_left);
    for (int y = 0; y < (int)b->rows; ++y) {
        for (int x = 0; x < (int)b->width; ++x) {
            unsigned char v = b->buffer[y * b->pitch + x];
            putchar(v > 200 ? '#' : v > 100 ? '+' : v > 30 ? '.' : ' ');
        }
        putchar('\n');
    }
    return 0;
}
```
