# M14 FreeText RTL appearance stream (WS-B) — SOURCE-VERIFIED design (2026-08-08)

Status: design fully re-verified against LIVE source at `e667fe0a` (branch
`m14/freetext-ap`, tree clean). RED/GREEN implementation NOT yet landed — the
first re-dispatch exhausted its tool budget re-verifying this map before writing
code. Use this file as the implementation contract; do NOT re-derive.

## Where the RTL branch goes (verified)

- `PDFDocumentBuilder::updateAnnotationAppearanceStreams(PDFObjectReference)` —
  pdfdocumentbuilder.cpp:1489. Insert the FreeText RTL early-return AFTER the
  highlight block (:1497-1505):
  ```cpp
  if (const PDFFreeTextAnnotation* freeTextAnnotation =
          dynamic_cast<const PDFFreeTextAnnotation*>(annotation.data()))
  {
      if (freeTextAnnotation->getContents().isRightToLeft())
      {
          if (updateRtlFreeTextAnnotationAppearanceStream(annotationReference, freeTextAnnotation))
          {
              return;
          }
      }
  }
  ```
  Fall through keeps the LTR QPainter path byte-identical.
- **NOT in `PDFFreeTextAnnotation::draw`** (pdfannotation.cpp:2713-2816): draw()
  receives only a QPainter backed by QPdfWriter inside PDFContentStreamBuilder
  (pdfdocumentbuilder.cpp:1526-1534) — a QPainter path cannot embed a
  Type0/FontFile2 dict into AP /Resources. This corrects the WS-B split-contract
  wording ("WS-B owns the FreeText AP path via pdfannotation.cpp draw").
- Mirror `updateHighlightAnnotationAppearanceStream` — declaration
  pdfdocumentbuilder.h:1645-1646, impl :1652-1794. AP form-stream construction
  pattern to copy:
  - resources dict (:1731-1741) → form dict `<< /Type /XObject /Subtype /Form
    /BBox <rect> /Resources <resources> >>` (:1743-1757)
  - `PDFObject::createStream(make_shared<PDFStream>(PDFDictionary(*formDict), content))`
    → `addObject` (:1766-1767)
  - annotationFactory `/AP << /N <formRef> >>` + `/Rect` → `mergeTo(annotationReference, ...)`
    (:1769-1792).

## Source-verified API map (exact signatures)

- `pdf::PDFRTLTextEngine::create(Settings, QByteArray fontKey)` (pdfrtltextengine.h:81;
  impl pdfrtltextengine.cpp:114) → `Result{ PDFDictionary fontDictionary; QByteArray
  contentFragment; bool hasRTL; QStringList errors; }`. fontDictionary has a SINGLE
  entry: `fontKey -> Type0 dict` (:690-692). Fragment is `BT..ET`, visual order,
  `/ActualText` BDC/EMC around RTL runs, uses the font key as `/<key> <size> Tf`
  (:402); hasRTL set per RTL run (:434); errors on unreadable font data (:122-126).
- `Settings` fields (h:54-61): text (LOGICAL order), language ("ar"/"fa"/"he"),
  fontSize (PDFReal, default 12.0), x, y (run origin; design uses 0,0 — text lands
  at the form BBox's bottom-left, acceptable per design), fontData (TTF bytes),
  fontFamily (descriptor BaseFont string).
- `PDFFreeTextAnnotation` (pdfannotation.h:868): `getContents()` inherited from
  PDFAnnotation (h:547, `const QString&`), `getDefaultAppearance()` (:890),
  `getRectangle()` (:546), `getJustification()` (:891).
- `PDFAnnotationDefaultAppearance::parse(QByteArray)` (h:452, impl :2653) →
  `getFontSize()` (default 8.0), `getFontName()` (e.g. "Helvetica"), `getFontColor()`.
  Fallbacks per design: fontSize 12, fontFamily "Helvetica"→"NotoNaskhArabic".
- RTL detection: `QString::isRightToLeft()` — precedent pdfwidgettool.cpp:912.
  Returns true if ANY strong RTL char (DirR/DirAL); mixed strings route to the
  RTL branch too and the engine shapes runs correctly (hasRTL only for RTL runs).
- `PDFDocumentBuilder::replaceObjectsByReferences(PDFDictionary&)` (h:353) — makes
  nested streams (FontFile2/CIDToGIDMap/ToUnicode) indirect objects in the builder
  storage; call on a copy of `rtlResult.fontDictionary` before embedding.
- `PDFObjectFactory::operator<<(PDFDictionary)` EXISTS (pdfdocumentbuilder.h:141,
  takes by value) — embeds the engine font dict as a direct dict value:
  `resourcesFactory << fontDictionary` inside a `"Font"` dict item.
- Annotation creation: 6-arg `createAnnotationFreeText(page, rect, title, subject,
  contents, TextAlignment)` (pdfdocumentbuilder.cpp:3503) → style overload (:3514).
  DA comes from `createFreeTextDefaultAppearance(createDefaultFreeTextStyle(...))`;
  `PDFFreeTextStyle` defaults = Helvetica / 10.0 / black / AlignLeft|AlignTop
  (pdfannotation.h:62-70). It calls `updateAnnotationAppearanceStreams(annotationObject)`
  ITSELF (:3574) — no extra call needed.
- `PDFDocumentModifier` (pdfdocumentbuilder.h:1667-1696): ctor takes `const
  PDFDocument*`, `getBuilder()`, `finalize()` (impl :2585: `m_builder.build()`,
  doc changed → `getDocument()`), `getDocument()` → PDFDocumentPointer.
- Reader/writer: `PDFDocumentReader::readFromFile/readFromBuffer`
  (pdfdocumentreader.h:64/74); `PDFDocumentWriter::write(fileName, document,
  safeWrite)` (pdfdocumentwriter.h:55); `PDFOperationResult` has `operator bool`
  + `getErrorMessage()` (usage pattern pdftooladdtext.cpp:400-409).
- Reopen walk: `getCatalog()->getPage(0)` (pdfcatalog.h:614) → `PDFPage::getAnnotations()`
  (pdfpage.h:184, `std::vector<PDFObjectReference>`) → `PDFAnnotation::parse(&storage,
  ref)` (pdfannotation.h:592) → `getContents()` for the logical-order assert.
  `PDFObjectStorage::getObject(ref)` (pdfdocument.h:82); `PDFDictionary::get/hasKey/
  getCount/getKey/getValue` (pdfobject.h:376-429).

## RED test recipe (core-level — NO CLI, no QProcess)

`src/UnitTests/tst_rtlfreetexttest.cpp`, registered like UnitTestsActualText
(src/UnitTests/CMakeLists.txt:167-187): `add_executable` + link `Pdf4QtLibCore
Qt6::Core Qt6::Gui Qt6::Test` + compile defs `TEST_BLANK_PDF` + `TEST_FONT_ARABIC`
+ `set_tests_properties(... ENVIRONMENT "QT_QPA_PLATFORM=offscreen")` + end with
`QTEST_GUILESS_MAIN(Class)` + `#include "tst_rtlfreetexttest.moc"`. No
`add_dependencies(... albdf)` needed (no CLI). Includes: pdfdocumentreader.h,
pdfdocumentwriter.h, pdfdocumentbuilder.h, pdfdocument.h, pdfpage.h, pdfannotation.h.

Flow: read `TEST_BLANK_PDF` → `PDFDocumentModifier` → `builder->createAnnotationFreeText(
pageRef, QRectF(...), "title", "subj", QString::fromUtf8("سلام"),
TextAlignment(Qt::AlignLeft|Qt::AlignTop))` → `modifier.finalize()` →
`PDFDocumentWriter(nullptr).write(outPath, modifier.getDocument().data(), true)` →
reopen → page 0 → annotations (expect size 1) → assert `getContents() == "سلام"`.

AP walk to assert:
`storage.getObject(annotRef).getDictionary()->get("AP")` → dict → `"N"` →
isReference → `storage.getObject(ref)` → isStream → `getStream()->getDictionary()`
→ `"Resources"` → dict → `"Font"` → dict → iterate `getCount()/getKey(i)/getValue(i)`
(resolve refs via storage) → assert ∃ entry with `/Subtype /Type0` AND its
`/FontDescriptor` → `/FontFile2` non-null.

Baseline RED behavior: the QPainter/QPdfWriter path emits a base-14 Helvetica
(or nothing) in AP resources — no /Type0, no /FontFile2 → assertion fails as
expected (the test targets the RIGHT failure).

## GOTCHA discovered (deviates from the WS-A RED-test recipe)

The RTL branch is compiled into the **core lib** (pdfdocumentbuilder.cpp), and
`src/Pdf4QtLibCore/CMakeLists.txt` currently has NO `target_compile_definitions`
at all — `TEST_FONT_ARABIC` exists only on UnitTests targets. The branch needs
the TTF path at compile time → either add
`target_compile_definitions(Pdf4QtLibCore PRIVATE TEST_FONT_ARABIC="<src>/tests/fonts/NotoNaskhArabic-Regular.ttf")`
or plumb a font-path constant into the builder. Open decision at GREEN time
(affects the GUI build too — the def is harmless there).

## Non-issues (do not over-engineer)

- Font-key collision: the AP form /Resources are built FRESH in this branch
  (single F2 entry) — the F1/F2 collision-scan from pdftooladdtext.cpp:217-268
  is NOT needed.
- LTR regression guard: existing 16/16 baseline covers the unchanged LTR path.
- pdfdocumentbuilder.cpp uses CRLF line endings (vendored upstream) — preserve
  surrounding lines' line endings when patching.
