# P3 render-probe calibration (Phase-1 RED evidence)

All numbers verified 2026-08-05 against the CURRENT emitter (yOffset
captured at `pdfrtltextengine.cpp:356-357`, discarded at 467-474),
`Vazirmatn-Regular.ttf`, 24pt at (72,700) on `blank.pdf`, rendered via
`albdf render --page-first 1 --page-last 1 --image-format png
--image-res-dpi 72` (72 dpi ⇒ 1 PDF pt = 1 px), 612x792 page, baseline at
image row ~92 (792 − 700).

## GPOS offsets (uharfbuzz, engine-equivalent buffer setup)

Engine setup to replicate (pdfrtltextengine.cpp:128-256): hb font scale
(upem, upem), `hb_ot_font_set_funcs`, dir=RTL, script=arab, lang=fa,
cluster level MONOTONE_CHARACTERS, no features. Vazirmatn upem = 2048.

- `مَا` (visual order, leftmost first): alef gid1173 x_adv 536 · **fatha
  gid728 x_adv 0, x_off +314, y_off −146** · meem gid1266 x_adv 1092.
  Fatha extents (xb 65, yb 1410, w 426, h −269): own ink 13.4–16.5px above
  baseline; with GPOS y_off −146 ⇒ 15.1–18.2px above (top ~2px above the
  alef's top).
- `بِسْم`: kasra gid731 x_off −84, **y_off −335**, extents (yb −236, h
  −269): own ink 2.8–5.9px below baseline; with GPOS ⇒ 6.7–9.8px below.
- Conversion: `px = fontUnits * pointSize / upem`; `imageRow = pageHpx −
  pdfY ± offsetFromBaseline` (above baseline = subtract).

## Renderer quirks (why you MUST calibrate empirically)

- The render pipeline RE-SHAPES text; it does not paint raw glyphs at
  content-stream positions. Evidence: `ما` and `اا` render pixel-identical
  composites; the fatha's diff ink appears as a ~14px-tall letterform-ish
  shape at rows 78–91 / cols 88–100, NOT the 5×3px glyph at the pen
  position; RTL text renders double-reversed (meem left of alef in `ما`).
- Single-glyph pages render completely BLANK (deterministic) — probes need
  ≥2-glyph strings (`اا` works where `ا` yields an empty PNG).
- The embedded "subset" font is the FULL font (gids unchanged;
  /CIDToGIDMap uses original gids), so uharfbuzz gid/extents analysis of
  the source TTF is valid for interpreting rendered PDFs. Mark codes have
  /W 0; the emitter ALSO discards xOffset for zero-advance marks (the
  `!qFuzzyIsNull(xOffset) && !qFuzzyIsNull(xAdvance)` guard), so marks are
  painted inline at the pen position.

## Verified band numbers (the RED test's calibration)

- `ما` (no mark): ink rows **75..91** — alef top at row 75.
- `مَا` − `ما` diff: rows **78..91** ⇒ above-band empty, overlaps core
  [77,89] ⇒ assertions (a)+(b) FAIL (this is the P3 symptom: mark at
  baseline).
- `بسم`: ink rows 75..91; `بِسْم` − `بسم` diff: rows 74..92 (includes
  layout-shift noise) ⇒ nothing below baseline ⇒ kasra assertion (c) FAIL.
- Post-fix expectation (H1 `rise = yOffset * fontSize / upem` = 1.71pt):
  fatha ink moves to rows ~74–77 ⇒ above row 75 and clear of the core ⇒
  test turns GREEN. H2 (`rise = yOffset/upem`, 0.07pt) would NOT clear the
  base top — the probe disambiguates the Ts unit convention by design.

## The RED test

`src/UnitTests/tst_rtladdtexttest.cpp::test_verticalMarkOffsets()` (Phase
1, commit `test(rtl): RED — vertical mark offset pixel-probe fails at
baseline (P3)`): helpers `inkRows(image)` / `diffRows(a,b)` in the file's
anonymous namespace; probes fatha (`مَا` vs `ما`) and kasra (`بِسْم` vs
`بسم`); asserts (a) diff ink in band [baseTop−6, baseTop−1], (b) no diff
ink in core [baseTop+2, baseBottom−2], (c) kasra diff ink at rows ≥
baseBottom+3. Runs `add-text --rtl --font TEST_FONT_PERSIAN --lang fa
--size 24` at (72,700) + `render` with the same flags as
`test_rtlRenderNoErrors`.

## uharfbuzz recipe notes

- Install: `pip install --user --break-system-packages uharfbuzz` (lands in
  system python3 only — the `execute_code` sandbox uses a different
  interpreter and will NOT see it; write probe scripts to /tmp and run them
  via terminal instead).
- API: `hb.ot_font_set_funcs(font)` — `font.funcs = hb.ot_funcs` was
  REMOVED in uharfbuzz 0.56 (AttributeError).
- `font.get_glyph_extents(gid)` → ink box in font units (y_bearing = top,
  negative height = extends downward); `get_nominal_glyph(cp)` for cmap
  lookups.
