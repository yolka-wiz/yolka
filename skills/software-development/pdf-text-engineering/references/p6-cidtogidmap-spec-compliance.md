# P6 — CIDToGIDMap spec compliance (wrong glyphs in every renderer)

Verified 2026-08-05 with Ghostscript (independent, spec-strict) + fontTools.
This is the corrected root cause for the P3 "vertical mark offsets" saga: the
~14px "oversized mark blob" that earlier investigation blamed on the RealText
renderer was actually **Latin 'A' (GID 2)** painted because the emitter's
CIDToGIDMap array is invalid per PDF spec and every strict renderer falls
back to Identity (CID == GID).

## The bug

`pdfrtltextengine.cpp` (emitter, ~lines 604–615) writes:

```
/CIDToGIDMap [0 681]              # single glyph "ا"
/CIDToGIDMap [0 1173 728 1266]    # three glyphs "مَا"
```

PDF 32000-1 §9.7.4.3: for a font with 2-byte CIDs, CIDToGIDMap must have
**65536 entries** (or be a stream). A short array is non-conformant:

- **Ghostscript**: rejects the short array → Identity mapping → CID 1 = GID 1
  = `.null` (no ink), CID 2 = GID 2 = Latin 'A' (15×17px at 24pt).
- **PDF4QT / albdf's own renderer**: `pdffont.cpp:2352–2359` reads
  CIDToGIDMap ONLY when `isStream()`; an array yields an empty mapping →
  same Identity fallback. So the project's own renderer agreed with
  Ghostscript: wrong glyphs everywhere.

## Evidence chain (all reproduced)

| Probe | Result |
|---|---|
| `gs` on real `alef.pdf` (add-text "ا") | **NO INK** (blank page) |
| `gs` on real `fatha.pdf` ("مَا") | ONE 15×17px blob = Latin 'A' shape |
| `gs` on real `meem.pdf` | NO INK |
| fontTools on embedded font | gid 1 = `.null`; gid 2 = `A` (Latin); gid 728 = `uni064E` (fatha, ink box y 1141..1410 of 2048 upem ≈ 5×3pt); gid 1173 = `uniFE8E` (alef); gid 1266 = `uniFEE3` (meem) |
| Ghostscript on `<02D8>` (=GID 728 via Identity) | **5×4px small mark** — the real fatha |
| Ghostscript on `<02D8>` + `2 Ts` | 5×4px mark, **rises 2px** (rows 75→73) — Ts mechanism works |
| Hand-patched 65536-entry stream on alef.pdf | Ghostscript paints the alef correctly (2×16px vertical stroke) |

Why golden tests missed it: golden images compare buggy-renderer output
against buggy-committed baselines (self-consistent); fetch-text/search use
ToUnicode + /ActualText (correct regardless of glyph mapping); RTL render
tests only assert exit code / no FreeType errors.

## The fix (verified direction)

Emit a **65536-entry stream** (2-byte big-endian per CID):

- entry[0] = 0 (.notdef)
- entry[code] = gid (from the existing `codeToGid` vector)
- all unused entries = 0
- 131072 bytes raw; Flate-compress if the factory supports it (zeros
  compress to near nothing). Matches the existing uncompressed ToUnicode
  style if no Flate helper is handy. Do NOT change the per-instance code
  scheme or /W widths.

Hand-patched proof: replaced array with `DecodedStreamObject` of 131072
bytes → Ghostscript painted the alef correctly.

## Debugging recipe (use before ever blaming a renderer)

1. Extract the embedded font (`FontFile2` from the descendant font's
   FontDescriptor) and dump `CIDToGIDMap` type/length + glyph order with
   fontTools (`getGlyphOrder()`, `BoundsPen`).
2. Render the SAME PDF with Ghostscript (`gs -q -dNOPAUSE -dBATCH
   -sDEVICE=png16m -r72 -sOutputFile=x.png x.pdf`) and compare ink bboxes
   with albdf's render. Disagreement → strict-vs-lenient difference.
3. "Oversized letterform blob where a small mark should be" or "single-glyph
   page blank" = Identity-fallback signature (Latin glyphs at low GIDs,
   `.null` at GID 1). Check the CIDToGIDMap FIRST.

## Probe tools note

- pypdf lives in SYSTEM python (`/usr/bin/python3`), PIL in the venv
  (`~/workspace/agent-env`). Use each where needed; don't assume one
  interpreter has both.
- Ghostscript (`/usr/bin/gs`) is a genuinely independent, spec-strict
  renderer — the right oracle for "does this PDF paint what I think".
- Hand-patched stream PDFs must fix `/Length` (PDF4QT reads `/Length`;
  Ghostscript scans for `endstream` — stale length silently breaks albdf
  renders while GS still works).
