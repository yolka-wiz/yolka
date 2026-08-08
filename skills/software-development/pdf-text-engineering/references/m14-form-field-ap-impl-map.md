# M14 form-field AP fix — verified implementation map (2026-08-08, WS-B recon)

Continuation task for the form-field appearance-stream fix. The parent orchestrator
said "do NOT re-explore; trust the prior agent's verified design" — this file is that
design, verified line-by-line from source. All file:line references were read from the
working tree at commit e667fe0a (branch m14/form-field-ap).

## The bug (baseline behavior, confirmed)

`albdf form-fill form.pdf filled.pdf --field name --value 'سلام'` exits 0 but the
output has `/V` and **NO `/AP`, NO `/FontFile2`, NO `/Type0`**. Two stacked causes:

1. **`PDFFormManager::drawFormField` (pdfform.cpp:914) is a `Q_UNUSED` no-op in core.**
   Real drawing exists only in the optional GUI's `PDFWidgetFormManager`
   (Pdf4QtLibWidgets/sources/pdfwidgetformmanager.cpp:2370).
2. **In the CLI path the builder's `m_formManager` is never set** — `pdftoolformfill.cpp`
   creates `PDFFormManager formManager(nullptr); formManager.setDocument(...)` (:147-148)
   but NEVER calls `modifier.getBuilder()->setFormManager(&formManager)`. So in
   `updateAnnotationAppearanceStreams`, `parameters.formManager = m_formManager` (nullptr),
   and `PDFWidgetAnnotation::draw` returns early at pdfannotation.cpp:3252-3255
   ("Do not draw without form manager") BEFORE even reaching the no-op drawFormField.

Consequence for the GREEN implementation: the RTL AP branch must NOT rely on
`m_formManager` being non-null. Either (a) set it explicitly in the CLI, or (b) read the
field dict directly from the builder's storage (widget dict has `/V` only when the widget
IS the field, e.g. fixture object 8; otherwise walk the `/Parent` chain). Option (b) is
more robust — it also survives GUI paths where the manager is set on a different document.

## Choke point call chain (verified)

- `PDFFormFieldText::setValue` (pdfform.cpp:983) → `builder->setFormFieldValue(...)` (:997)
  then per-widget `builder->updateAnnotationAppearanceStreams(formWidget.getWidget())` (:1003).
- `PDFDocumentBuilder::updateAnnotationAppearanceStreams` (pdfdocumentbuilder.cpp:1489):
  parse annotation (:1491) → highlight special-case (:1497-1505, pattern to MIRROR) →
  page/mediaBox checks (:1507-1518) → `annotation->getDrawKeys(m_formManager)` (:1520) →
  per-key `PDFContentStreamBuilder` + `AnnotationDrawParameters` + `annotation->draw()`
  (:1526-1533) → **bails on `!parameters.boundingRectangle.isValid()`** (:1536-1540) →
  build form XObject dict + `mergeTo(formReference, ...)` (:1551-1573) →
  AP dict assembly + `mergeTo(annotationReference, annotationFactory.takeObject())` (:1648).
- `PDFWidgetAnnotation::draw` (pdfannotation.cpp:3249): null-formManager early return
  (:3252-3255); text/choice fields call `parameters.formManager->drawFormField(formField,
  parameters, false)` (:3273-3280); buttons have their own branch (:3282+).

## Proven RTL emission template (add-text, pdftooladdtext.cpp:181-423)

1. Read TTF: `QFile fontFile(path); open(ReadOnly); fontData = readAll()` (:189-197).
2. `PDFRTLTextEngine::Settings`: `text` (logical), `language` ("fa"/"ar"/"he"/"ur"),
   `fontSize`, `x`, `y` (baseline), `fontData`, `fontFamily` (:200-207).
3. Pick a free font key `F<n>` (scan page /Resources Font dict, avoid collisions,
   :217-268 — for an AP form stream the /Resources dict is fresh, so a fixed key like
   "F2" is fine; the engine bakes the key into the fragment as `/F<n> <size> Tf`).
4. `PDFRTLTextEngine::create(settings, fontKey)` → `Result{fontDictionary, contentFragment,
   hasRTL, errors}`. `fontDictionary` is a ONE-entry dict `{fontKey: <Type0 font dict>}`
   (pdfrtltextengine.cpp:690-691). Check `errors.isEmpty()`.
5. `builder->replaceObjectsByReferences(fontDictionary)` (:282) — mutates in place,
   replaces each non-reference value with a ref to a newly added object.
6. Compress fragment: `PDFFlateDecodeFilter::compress(contentFragment)` (:287).
7. Content stream object: dict with `Length` + `Filter [FlateDecode]` +
   `PDFObject::createStream(...)` → `builder->addObject(...)` (:288-294, 382).
8. `mergeTo(targetRef, dict)` for the final merge (:1648 pattern).

## Builder/annotation APIs confirmed

- `replaceObjectsByReferences(PDFDictionary&)` — pdfdocumentbuilder.h:353 (mutates in place).
- `mergeTo(PDFObjectReference, PDFObject)` — pdfdocumentbuilder.h:452; implementation does
  `PDFObjectManipulator::merge(storage.getObject(ref), object, RemoveNullObjects)`.
- `addObject(PDFObject) -> PDFObjectReference` — pdfdocumentbuilder.h:412.
- `getObjectByReference`, `getDictionaryFromObject`, `getObject(PDFObject)` —
  pdfdocumentbuilder.h:366-374 (dereference-with-null-safe variants).
- `getFormManager()`/`setFormManager(const PDFFormManager*)` — pdfdocumentbuilder.h:389-390.
- `PDFObjectStorage::getTrailerDictionary()` — pdfdocument.h:108 (for AcroForm `/DA`
  fallback: trailer → /Root → /AcroForm → /DA; nullable at every hop).
- Widget rect: `PDFAnnotation::getRectangle()` (pdfannotation.h:546), /Rect parsed as
  `QRectF(xMin, yMin, xMax-xMin, yMax-yMin)` (pdfdocument.cpp readRectangle).
- Field value: `PDFFormField::getValue()` → `PDFObject::getString()` (raw bytes;
  makeValueObject in pdftoolformfill.cpp:85-99 writes `value.toUtf8()` — so /V bytes are
  UTF-8; check for FEFF BOM defensively, else `QString::fromUtf8`).
- DA: `PDFAnnotationDefaultAppearance::parse(QByteArray)` → `getFontName()` / `getFontSize()`
  (pdfannotation.h:445-458; parse default fontSize = 8.0 — task says fallback 12 when
  `qFuzzyIsNull`). Fixture AcroForm /DA = `(/Helv 0 Tf 0 g)` (object 6).
- Quadding: `PDFFormFieldText::getQuadding()` (pdfform.h:447, `std::optional<PDFInteger>`);
  field dict `/Q` 0=left 1=center 2=right; x anchored by run LEFT edge (engine starts
  cursorX at settings.x, pdfrtltextengine.cpp:404-413), so right-quadding needs
  `x = rect.right() - runWidth - pad` — runWidth unknown before create(); shape once with
  x=0 to measure or right-anchor after a first create() pass.

## Form field helper lookups (pdfform.h)

- `PDFFormManager::getFormFieldForWidget(PDFObjectReference)` — pdfform.h:458 (const) /
  463 (non-const); map built by `PDFFormField::fillWidgetToFormFieldMapping`
  (pdfform.cpp:171-182): `mapping[widget] = parent field`.
- `PDFForm::getDefaultAppearance()` / `getDefaultAlignment()` — used by GUI
  (pdfwidgetformmanager.cpp:1559-1560) as AcroForm-level DA fallback.
- `PDFFormField::getValue()` — pdfform.h:199; `PDFFormFieldText::getQuadding()`
  pdfform.h:447; `getDefaultAppearance()` pdfform.h:446.

## Test wiring (RED)

- Fixture: embedded form PDF at tst_formsignaturetest.cpp:72-110 — catalog/AcroForm
  object 6 (`/DA (/Helv 0 Tf 0 g)`), page 4, widget 7 (empty, /Rect [100 700 300 720]),
  text field `name` object 8 (widget+field merged, `/V (John)`), checkbox 10, choice 12.
- `runTool(toolPath, args, workDir)` helper exists (:149-165); binary found via
  `QCoreApplication::applicationDirPath() + "/albdf"`.
- CMake: `UnitTestsFormSignature` at src/UnitTests/CMakeLists.txt:242-257 —
  `target_link_libraries(... Pdf4QtLibCore Qt6::Core Qt6::Gui Qt6::Test)`,
  `add_test` + `set_tests_properties(... ENVIRONMENT "QT_QPA_PLATFORM=offscreen")`,
  `add_dependencies(UnitTestsFormSignature albdf)`. Add
  `target_compile_definitions(UnitTestsFormSignature PRIVATE
  TEST_FONT_ARABIC="${CMAKE_CURRENT_SOURCE_DIR}/../tests/fonts/NotoNaskhArabic-Regular.ttf")`
  after the link line (mirror TEST_FONT_PERSIAN at :149-150/:200-201). Font exists:
  src/tests/fonts/NotoNaskhArabic-Regular.ttf.

## CLI --font plumbing (mirror add-text)

- Options struct: pdftoolabstractapplication.h:196-199 (FormFill block) — add
  `QString formFillFont;`.
- Parser registration: pdftoolabstractapplication.cpp:215-221 (FormFill block) —
  `parser->addOption(QCommandLineOption("font", "TTF font file for RTL field appearance
  streams.", "file"))`.
- Value extraction: pdftoolabstractapplication.cpp:685-690 —
  `options.formFillFont = parser->value("font")`.
- Execute: pdftoolformfill.cpp — read TTF bytes early (before the setValue loop at :151),
  then either `modifier.getBuilder()->setFormManager(&formManager)` + a font-data member
  on the form manager, or a builder-side accessor (e.g. `setFormFieldRtlFontData(QByteArray)`)
  — the AP generator in updateAnnotationAppearanceStreams reads it.

## Session state at interruption (2026-08-08, WS-B)

- Only edit made: `test_formFillRtlAppearance();` slot declaration added to
  tst_formsignaturetest.cpp:44. NOT committed. No build/test run.
- RED test body, CMake def, GREEN implementation, PROBLEMS.md R#5 entry, and both
  commits were NOT done. Baseline: build dir src/build configured, 190/190 compiled,
  ctest 16/16 green.
