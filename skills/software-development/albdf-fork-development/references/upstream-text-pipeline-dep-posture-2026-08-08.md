# Upstream PDF4QT master: text pipeline + dependency posture (verified 2026-08-08)

Source-verified read-only map of `upstream/master` (JakubMelka/PDF4QT) — answers "how does
upstream render text" and "would harfbuzz+fribidi vcpkg deps be a red flag" for the RTL-engine
upstream-PR question. All paths at upstream root (NOT under `src/`); verify with
`git show upstream/master:PATH` from the albdf checkout. Upstream master as of 2026-08-08.

## 1. Text pipeline — glyph-level, NO shaping, NO QTextLayout

- `Pdf4QtLibCore/sources/pdftextlayoutgenerator.cpp` is a tiny `PDFPageContentProcessor`
  visitor. Only real behavior: `performOutputCharacter(const PDFTextCharacterInfo&)` (l.72)
  → `m_textLayout.addCharacter(info)`. `createTextLayout()` (l.29) =
  `m_textLayout.perform(); m_textLayout.optimize();`. No bidi/ligature/shaping logic at all.
- `PDFTextCharacterInfo` (`pdftextlayout.h:41-55`): `QChar character` + `QPainterPath outline`
  (vector glyph path) + `advance` + `fontSize` + `matrix`. Layout is built from per-glyph
  geometry, NOT font shaping.
- `PDFTextLayout` (`pdftextlayout.h:362`) = docstrum geometric clustering (`PDFTextBlocks
  m_blocks` l.445; settings l.56-77: samples, distanceSensitivity, line/block overlap).
  `PDFTextFlow::find` (`pdftextlayout.cpp`) = plain `m_text.indexOf` — the search primitive.
- **`QTextLayout` in ALL of core: exactly 2 hits** — `pdfform.h:32` (include) +
  `pdfxfaengine.cpp:12293-12294` (XFA appearance). Extraction never touches it.
- **`QPainter::drawText` in core = render-only, never extraction:**
  - `pdfpagecontentprocessor.cpp:3253` `drawText(TextSequence)` — the optional `RealText`
    renderer feature (`PDFRenderer::RealText`, `pdfrenderer.h:76`): paint with substituted
    QFont instead of vector paths.
  - `pdfannotation.cpp:2815, 3317` (FreeText annotation / widget AP drawing),
    `pdfxfaengine.cpp` (XFA), `pdfpainter.cpp:315`, `pdfpainterutils.cpp:68`,
    `pdfblpainter.cpp:1236` (Blend2D engine drawTextItem override).

## 2. Font realization — FreeType, glyph 1:1, already a dependency

- `pdffont.cpp` includes ft2build/freetype (l.30-35), **114 `FT_*` call sites**.
  `PDFRealizedFontImpl` wraps an `FT_Face`: `FT_New_Memory_Face` (:1681 embedded, :1711
  system, :2129), `FT_Load_Glyph` (:1386, :1566), `FT_Outline_Decompose` (:1567, glyph →
  QPainterPath), `FT_Get_Glyph_Name` (:1595, :2167).
- `pdffont.h` class map: `PDFFont`(:311) → `PDFSimpleFont`(:370) → `PDFType1Font`,
  `PDFTrueTypeFont`(:453), `PDFType3Font`(:717), `PDFType0Font`(:762); `PDFFontCMap`(:596),
  `PDFFontCMapRepository`(:815), `PDFSystemFont`(:840). `PDFFontCache`(:463) caches fonts +
  realized fonts; `getFontForTextDrawing`(:488) → substituted QFont for RealText only.
- No HarfBuzz, no FriBidi, no GSUB/GPOS anywhere — glyph IDs resolved 1:1 via
  CMaps/ToUnicode and handed straight to FT_Load_Glyph.

## 3. Dependency posture

- `vcpkg.json` (root): `{ "name": "pdf4qt", "version-string": "1.5.2", "dependencies": [
  "tbb","openssl","lcms","zlib","openjpeg","freetype","libjpeg-turbo","libpng","blend2d" ] }`
  — exactly the 9 deps. **Qt deliberately NOT in the manifest** (installed via
  jurplel/install-qt-action in CI).
- History: **8 commits ever touched vcpkg.json**, each feature-driven (blend2d =
  "Alternative software rendering backend", tbb = multithreading, jpeg = "ijg-libjpeg
  obsoleted in vcpkg"...). **version-string is stale (1.5.2 vs release 1.6.0.0)** — the
  manifest is a stable fixture the maintainer doesn't bump per release.
- `Pdf4QtLibCore/CMakeLists.txt:183`: `target_link_libraries(Pdf4QtLibCore PRIVATE Qt6::Core
  Qt6::Gui Qt6::Xml Qt6::Svg)` + LCMS2, OpenSSL::SSL/Crypto, ZLIB::ZLIB, Freetype::Freetype,
  openjp2, JPEG::JPEG, blend2d::blend2d, TBB (PUBLIC, Linux-only). **No Concurrent/Widgets
  in core** (GUI dirs only). Source list is explicit + alphabetically sorted, NOT globbed;
  `pdftextlayoutgenerator.{h,cpp}` at l.153-154.
- CI (`.github/workflows/ci.yml`): vcpkg manifest mode (`vcpkg install
  --x-manifest-root=...`; cache key = hashFiles('**/vcpkg.json')); **no `pull_request`
  trigger** — push-to-master + workflow_dispatch only, so external PRs are NEVER
  build-validated by CI; the maintainer reviews the diff by eye.
- README: MIT since 2025-04-27 (§:32-34), contributions welcome no CLA (:79-82), third-party
  libs listed in §4 (:69-75: FreeType, OpenJPEG, Qt, OpenSSL, LittleCMS, zlib, Blend2D).

### Dep-add risk for harfbuzz+fribidi = MEDIUM (not red-flag, not free)

- NOT a red flag: project policy is "add the standard library when a feature needs it"
  (blend2d/tbb/openjpeg entered that way); **HarfBuzz is the canonical companion to the
  already-linked FreeType** (HarfBuzz MIT, FriBidi LGPL-2.1+ as a separate linked C library —
  fine under MIT, but must be listed in README §4); both are small, dependency-light
  (FriBidi has none; harfbuzz glib/icu are optional vcpkg features), cross-platform; CI
  picks them up with zero workflow changes.
- Visible/social: manifest is minimal + stable (see above); the maintainer's obvious counter
  is **"Qt 6 already bundles HarfBuzz and FriBidi internally — why new deps?"**. The
  rebuttal that carries the PR: Qt's text engine hides exactly what a PDF writer needs —
  per-character bidi levels, glyph clusters (ToUnicode//ActualText mapping), GPOS offsets —
  and PDF4QT's stack is FreeType-based, so QTextLayout would be a second, parallel text
  stack. No CI on PRs → lead with a design note; keep the dep surface to default-feature
  harfbuzz + fribidi.

## 4. Qt-native (QTextLayout+QRawFont) vs explicit harfbuzz+fribidi

| Criterion | Qt-native | harfbuzz+fribidi |
|---|---|---|
| New deps | none | +2 manifest + README |
| Bidi levels per char | hidden (QTextLayout exposes lines/glyph runs, not levels) | fribidi_get_par_embedding_levels_ex — full |
| Glyph clusters (ToUnicode//ActualText) | **not exposed** by QGlyphRun — must re-derive | hb_buffer clusters — exact |
| GPOS y-offsets (Arabic marks) | QGlyphRun::positions() 2D pen positions, awkward | direct buffer offsets (what albdf already emits) |
| Fit with existing stack | second parallel text stack | extends the existing FreeType pipeline |
| PDF emission | needs reconstruction; screen-only naturally | direct BT/Tj/TJ + CIDToGIDMap |

Verdict: Qt-native wins only on "zero dep diff" optics; it is the wrong tool for PDF
content-stream emission. Explicit deps are the technically defensible choice — risk is
social, not technical.

## 5. Existing RTL/Arabic/Persian issue evidence (upstream = greenfield)

- **Issue #240** "Hebrew filename is displayed incorrectly" (2025-02-04 → closed 2025-07-19):
  GUI title-bar/filename display bug, NOT PDF text. Maintainer asked for repro, user lost
  their machine, maintainer closed after ~6 months ("No response for about a half of the
  year"). Never fixed.
- **Issue #228** "[feature] reverse pages order" (2024-12-02): only issue under
  arabic/persian search — page order UX, not text.
- GitHub commit search: **0 commits** match hebrew / arabic+rtl / bidi. No rtl/bidi issues
  at all. RTL PDF text = uncontested new value.
- Only "RightToLeft" token in core: `pdfcatalog.cpp:403` = `/ViewerPreferences /Direction`
  **page-spread direction**, not text bidi.

## 6. Integration map for a PDFRTLTextEngine on upstream master

1. New files `Pdf4QtLibCore/sources/pdfrtltextengine.{h,cpp}` (+ normalizer) — same dir as
   all PDF* classes.
2. Register in `Pdf4QtLibCore/CMakeLists.txt` add_library list (explicit, non-globbed;
   insert near pdftextlayoutgenerator.cpp l.153-154). Export via existing
   PDF4QTLIBCORESHARED_EXPORT. **No new Qt modules needed** (Core+Gui already PRIVATE).
3. Write-side hook: `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
   (upstream `pdfdocumentbuilder.cpp:1467`; fork's :1489 = same fn + fork lines). The
   additive early-return pattern `updateHighlightAnnotationAppearanceStream` (:1474-1480) is
   the shape to mirror: engine create → `replaceObjectsByReferences` (:1073) → form XObject
   → `mergeTo(ref, /AP)`. One choke point covers FreeText AND form-field APs
   (PDFFormFieldText::setValue → setFormFieldValue → updateAnnotationAppearanceStreams).
4. Read-side hooks: `PDFDocumentTextFlowFactory` (`pdfdocumenttextflow.cpp:704` builds
   PDFTextLayoutGenerator; GUI pdfcompiler.cpp:442/574 too), `PDFTextLayoutGenerator::performOutputCharacter`
   (overlay point), `PDFTextFlow::find` (plain indexOf — search hook).
5. Tests in upstream `UnitTests/`; README §4 + license attributions must grow.

## 7. Measurement trap (hit 2026-08-08)

Case-insensitive `git grep -i 'RTL'` / `-i 'SearchEngine'` matches `startLineEnding` (the
"rtL" substring) across pdfannotation.cpp etc. — false positives. The only REAL tokens in
core: `Direction::RightToLeft` (page spread, pdfcatalog.cpp:403) and `getFontForTextDrawing`
comments. Always confirm a grep hit by reading the line; don't trust `-l` file lists from
case-insensitive 3-letter patterns.

## Verification recipe

```bash
cd /home/agent/workspace/al-bdf-engine
git show upstream/master:vcpkg.json
git show upstream/master:Pdf4QtLibCore/CMakeLists.txt | sed -n '180,190p'
git show upstream/master:Pdf4QtLibCore/sources/pdftextlayoutgenerator.cpp
git grep -n "QTextLayout\|drawText" upstream/master -- Pdf4QtLibCore/sources/ | head
git grep -n "FT_" upstream/master -- Pdf4QtLibCore/sources/pdffont.cpp | head
git log --oneline upstream/master -- vcpkg.json
```
