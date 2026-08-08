# M14 WS-B — RTL FreeText annotation appearance (design VERIFIED, NOT implemented)

Session 2026-08-08. Worktree `/home/agent/workspace/wt-m14-freetext`, branch `m14/freetext-ap`
(base origin/main @ e667fe0a). Baseline built (Release, vcpkg) + `ctest` 16/16 green. The session
hit its tool-iteration cap BEFORE writing any code/commits — this file is the verified design so a
continuation agent can execute without re-exploration. **The GREEN implementation below was
designed but never built/tested — treat it as a validated plan, not validated code.**

## Verified structural blocker (why the branch can't live in draw())
`PDFFreeTextAnnotation::draw` (src/Pdf4QtLibCore/sources/pdfannotation.cpp:2713) receives ONLY a
`QPainter` backed by `QPdfWriter` inside `PDFContentStreamBuilder` (pdfdocumentbuilder.cpp:1526-1534).
A QPainter path cannot inject a Type0/FontFile2 font dict into the AP `/Resources` — so the RTL
branch CANNOT live inside `draw()`. It must live in the FreeText AP generation path:
`PDFDocumentBuilder::updateAnnotationAppearanceStreams` (pdfdocumentbuilder.cpp:1489), as a strictly
additive early-return branch mirroring the existing highlight branch. This satisfies the WS split
contract ("generic annotation-draw RTL hook, additive only").

## Verified choke-point map (all line numbers read from source this session)
- `updateAnnotationAppearanceStreams`: pdfdocumentbuilder.cpp:1489-1650
  - highlight early-return branch (the pattern to mirror): 1497-1505
  - generic loop → `annotation->draw` at :1533 → `PDFContentStreamBuilder` (QPdfWriter) → form XObject :1526-1575
  - `/AP` attach via `mergeTo(annotationReference, ...)`: 1635-1648
- `updateHighlightAnnotationAppearanceStream` (template for the new method): :1652-1794
  - form stream build `<< /Type /XObject /Subtype /Form /BBox <rect> /Resources ... >>`: 1743-1767
  - `mergeTo` `/AP`: 1769-1792
- `replaceObjectsByReferences`: :1095-1106 — converts nested FontFile2/CIDToGIDMap/ToUnicode streams
  to object refs. **REQUIRED** before embedding the engine's font dict (same step the CLI does).
- FreeText creation call sites (each ends with `updateAnnotationAppearanceStreams`): :3419 (callout
  overload), :3514/:3522 (style overload), :3579
- `PDFRTLTextEngine::create(settings, fontKey)` → `{fontDictionary (Type0 + FontFile2 subset),
  contentFragment (BT..ET, visual order, /ActualText BDC), hasRTL, errors}` — pdfrtltextengine.h:81.
  Fragment emits `/<fontKey> <size> Tf`, absolute `Tm`, NO color operator → prepend DA color (`rg`).
- DA parse: `PDFAnnotationDefaultAppearance::parse(getDefaultAppearance())` → `getFontSize()` /
  `getFontColor()` (pdfannotation.h:445-462)
- CLI-proven font load + engine call: src/PdfTool/pdftooladdtext.cpp:197-282 (TTF `readAll()`,
  fontKey "F2", `replaceObjectsByReferences(fontDictionary)` before merge)

## GREEN design (additive, minimal — form-field branches untouched)
In `updateAnnotationAppearanceStreams`, after the highlight branch:
```cpp
if (const PDFFreeTextAnnotation* ft = dynamic_cast<const PDFFreeTextAnnotation*>(annotation.data()))
{
    if (updateFreeTextAnnotationAppearanceStream(annotationReference, ft))
        return;
}
```
New private method `updateFreeTextAnnotationAppearanceStream` (mirror highlight; returns false to
fall through to the untouched QPainter path when contents is NOT `isRightToLeft()` or no Arabic TTF
is available):
1. Read the Arabic TTF (test: `TEST_FONT_ARABIC` = NotoNaskhArabic-Regular.ttf; CLI pattern pdftooladdtext.cpp:197).
2. `PDFRTLTextEngine::Settings`: `text = contents` (LOGICAL — `/Contents` stays logical per spec),
   `language = "ar"`, `fontSize` from DA `getFontSize()`, `fontFamily` from DA font name (fallback
   "Helvetica"), origin (0,0) in form space.
3. `create(settings, "F2")` → `replaceObjectsByReferences(result.fontDictionary)` →
   resources `<< /Font <fontDictionary> >>`.
4. Form stream + `mergeTo` `/AP` exactly per highlight template :1743-1792.

## RED test recipe (core-level; no CLI needed)
`src/UnitTests/tst_rtlfreetexttest.cpp` + CMakeLists entry (template: `UnitTestsActualText` block,
src/UnitTests/CMakeLists.txt:167-187 — add_executable, link `Pdf4QtLibCore Qt6::Core Qt6::Gui
Qt6::Test`, compile defs `TEST_BLANK_PDF` + `TEST_FONT_ARABIC`, offscreen ENV, add_test).
Flow: `PDFDocumentReader::readFromBuffer(blank.pdf)` → `PDFDocumentModifier::getBuilder()` →
`builder->createAnnotationFreeText(pageRef, QRectF(100,100,200,80), title, subject,
QString::fromUtf8("سلام"), TextAlignment(Qt::AlignLeft|Qt::AlignTop))` → `builder->build()` →
`PDFDocumentWriter::write(QIODevice*)` to `QTemporaryDir` → reopen → `PDFPage::getAnnotations()` →
`PDFAnnotation::parse(&storage, ref)` → `getAppearanceStreams().getAppearance(Normal)` → resolve ref →
form stream dict → `/Resources /Font` → assert a font entry has `/Subtype /Type0` AND its
`/FontDescriptor` has `/FontFile2`. Baseline fails: current AP resources only carry the
QPdfWriter-emitted Helvetica (base-14, no FontFile2).

## Baseline facts (verified this session)
- ctest 16/16 green at e667fe0a; commit message for GREEN: `fix(core): RTL FreeText annotation appearance via PDFRTLTextEngine (M14)` (RED test as a separate commit first).
- `docs/PROBLEMS.md` has NO FreeText/tofu entry (grep → 0 hits) — add one under "RTL rendering
  limitations" (R#1-R#4 area) with commit refs when the fix lands.
- `db/albdf.db` has no freetext task (`python3 scripts/db.py search freetext` → no matches).
- vcpkg: `/home/agent/vcpkg-cache/vcpkg` (NOT `/workspace/vcpkg` as AGENT.md claims).
- WORKTREE ONLY: `/home/agent/workspace/wt-m14-freetext`, never the main checkout. Split contract:
  WS-A owns form-field AP branches + `pdftexteditpseudowidget.cpp` — do NOT touch them.
- git identity for commits: `git -c user.name=yolka -c user.email=yolka@albdf.local`;
  run `python3 scripts/gen-repo-map.py` before committing if tracked files were touched.

## Remaining steps (for the continuation agent)
1. Write RED test + CMake registration → build → confirm it FAILS (no Type0/FontFile2 in AP resources) → commit RED.
2. Implement GREEN branch → build → `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build --output-on-failure` (expect 17/17) → commit GREEN.
3. Update `docs/PROBLEMS.md` (FreeText tofu gap resolved + commit refs).
