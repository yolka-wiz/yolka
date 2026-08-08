# /ActualText payload is VISUAL order — correction (2026-08-07)

**Correction to the claim in SKILL.md that `/ActualText` marked content carries
"the logical string".** It does not. The payload is built from each glyph's
FULL cluster text **in GLYPH (visual, leftmost-first) order**:

`src/Pdf4QtLibCore/sources/pdfrtltextengine.cpp` (~417-424), in the run
emission:
```cpp
// /ActualText: UTF-16BE with BOM, built from each glyph's FULL
// cluster text IN GLYPH (visual, leftmost-first) ORDER — not the
// logical run text. ...
QByteArray actualText;
actualText.append(char(0xFE)); actualText.append(char(0xFF));
for (const ShapedGlyph& glyph : run.glyphs)
    actualText.append(glyph.unicode);
content += QStringLiteral("/Span << /ActualText <%1> >> BDC\n")
               .arg(QString::fromLatin1(actualText.toHex().toUpper()));
```

## Why this matters

- The overlay (commit 800f91ec, `PDFTextLayoutGenerator::performMarkedContentEnd`)
  repairs ligature degradation (P1: `لا`→`ل`) and yeh duplication (P2) — but the
  repaired string is in **visual order** for RTL runs.
- CLI search works because `PDFTextSearchEngine` inverts the QUERY to visual
  (`invertToVisual()` via `fribidi_log2vis`) before matching — it does NOT
  re-invert the document text.
- Any consumer that shows or copies extracted RTL text (GUI clipboard copy via
  `PDFTextLayout::getTextFromSelection`, `PDFSelectTextTool::performCopy`) gets a
  visual-order (reversed) string and needs `invertToVisual`-style inversion.

## GUI consequences (summary)

- GUI search (`PDFAdvancedFindWidget::performSearch`, `PDFFindTextTool::performSearch`)
  calls `PDFTextLayoutStorage::find` → `PDFTextFlow::find` = plain
  `m_text.indexOf(...)` — NOT `PDFTextSearchEngine` (referenced nowhere in the GUI).
- GUI text layout uses OUR `PDFTextLayoutGenerator` (pdfcompiler.cpp:442), so the
  overlay feeds selection/highlight/copy automatically; only inversion + search
  engine wiring are missing.

Full integration map (add-text paths, R#4 fix location, integration-points
table): `albdf-fork-development` → `references/rtl-through-gui-integration.md`.

NOTE (2026-08-07): this file could not be linked from SKILL.md because the
curator read-before-write guard + view dedup blocked body patches this session.
A foreground session should add one line to SKILL.md's Core-model section:
"/ActualText payload is in GLYPH (visual) order, not logical — see
references/actualtext-visual-order.md."
