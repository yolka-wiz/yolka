# P3 — Vertical mark offsets (planned 2026-08-05, not yet implemented)

## Symptom
Arabic/Persian diacritics (fatha, kasra, damma, sukūn) and Hebrew niqqud
render **at the baseline**, painted over the base letter, instead of above
it. Example: `بِسْم` — the kasra overlaps the `ب`.

## Root cause (verified in code)
`src/Pdf4QtLibCore/sources/pdfrtltextengine.cpp`:
- Lines 356–357: HarfBuzz GPOS anchor offsets ARE captured per glyph:
  `glyph.xOffset = PDFReal(glyphPos[g].x_offset); glyph.yOffset = ...`
- Lines 467–474: the emitter folds `xOffset` into TJ numeric spacing but
  **discards `yOffset`** — a TJ array's numeric items are horizontal
  displacements only; there is no per-glyph vertical offset in a TJ array.

## Fix design — text rise (`Ts`)
PDF 32000-1 §9.4.2: `Ts` = "distance, in unscaled text space units, to move
the baseline up or down from its default location", added to the `ty`
component of the text line matrix; affects subsequently painted glyphs until
reset to 0.

Emission per glyph with non-zero `yOffset`:
1. Flush the current hex run (close TJ if open).
2. `rise = yOffset * fontSize / upem` (font units → PDF points).
3. `rise Ts` → mark glyph as single-glyph string → `0 Ts`.
4. Continue the run; reopen TJ for the rest.

Why this over alternatives:
- **No `Tm` boundary** → PDF4QT flow/extraction does NOT insert a phantom
  space (the code comment at lines 438–440 warns Tm splits break
  extraction).
- Zero-advance marks keep their inline x position; only the baseline rises.
- `/ActualText` wrapper untouched → logical text extraction unchanged.

**Verify the unit conversion empirically** (pixel probe: render `مَا` at
24pt, assert ink in the band above the base letter's ascender) — whether
`Ts` is pre- or post-`Tfs` multiplication must be pinned by the golden test,
not assumed.

## TDD steps
1. RED: `tst_rtladdtexttest.cpp::test_verticalMarkOffsets` — add-text
   `مَا` (fatha) + `بِسْم` (kasra) at 24pt onto blank.pdf, render page 1 to
   PNG, probe pixels: ink above base letter's x-range, no ink at baseline
   where the mark would be. Expect FAIL.
2. GREEN: implement `Ts` emission; full rtl suite + ctest 11/11 still green.
3. No-regression: fetch-text intact (no phantom spaces); search `ما`/`بسم`
   (marks stripped by normalization) → 1 match; non-mark golden images
   unchanged.
4. Docs + DB: PROBLEMS.md P3 resolved, README/RELEASES, db/seed.py task
   closed.
5. Gate + push: ci/run-ci.sh all green, live CLI check.

## Risks
| Risk | Mitigation |
|---|---|
| `Ts` unit convention wrong (pre/post Tfs) | pixel-probe pins exact value |
| `Ts` causes flow/extraction phantom spacing | Ts moves baseline only; verify fetch-text in step 3; fallback = keep inline (status quo) |
| Multi-mark stacking (fatha + shadda) | per-glyph Ts toggles handle it; add stacked case if needed |
| Fonts without GPOS mark anchors | yOffset==0 → no Ts emitted; unchanged (verify with Noto Naskh Arabic) |
| Search regression (S#1 interplay) | mark glyph zero advance, same x → stays in same flow item; step 3 tests search on mark text |

## Out of scope
LTR runs (Helvetica has no marks); reordering/stacking beyond GPOS anchor
positions; GUI (ADR-0002).
