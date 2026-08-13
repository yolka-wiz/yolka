# M14 WS-A: RTL form-field appearance streams — session record (2026-08-08)

Session: delegated WS-A task on `m14/form-field-ap` (worktree
`/home/agent/workspace/wt-m14-forms`, base `origin/main e667fe0a`). The session
hit its tool budget BEFORE implementing GREEN — everything below is VERIFIED
(source reads + real builds/runs) up to the point stated; the GREEN design was
a plan, not a tested result. **GREEN since 2026-08-08: fix `21c42879` + docs
`285deab9` — see `form-field-rtl-appearance-green-m14.md` in this directory.**

## Verified facts (do not re-verify)

### Build + baseline
- Configure: `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg && cmake -S src -B
  src/build -G Ninja -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake
  -DALBDF_BUILD_TESTS=ON` → OK (3.5s).
- `cmake --build src/build -j$(nproc)` → 190/190 targets, exit 0.
- `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build --output-on-failure` →
  **16/16 passed** at baseline (UnitTests, UnitTestsRtlNormalizer,
  UnitTestsImageOptimizer, UnitTestsFontEncoding, UnitTestsRecognizeText,
  UnitTestsDeleteObject, UnitTestsAddText, UnitTestsRtlAddText,
  UnitTestsActualText, UnitTestsSearchText, UnitTestsGolden,
  UnitTestsFormSignature, UnitTestsPageOps, UnitTestsRedact, UnitTestsRender,
  SmokeCli).

### Empirical probe (real CLI run, temp fixture replicating tst_formsignaturetest)
```
albdf form-fill form.pdf filled.pdf --field name --value 'سلام'
```
exit 0; `filled.pdf` = 1694 bytes; object 8 in output:
`<< /FT /Tx /T (name) /V (\xD8\xB3\xD9\x84\xD8\xA7\xD9\x85) /Type /Annot
/Subtype /Widget /Rect [ 100 700 300 720 ] ... >>`
- Output contains: `/V` raw UTF-8 bytes of سلام ✓ (logical order preserved)
- Output does NOT contain: `/AP`, `/FontFile2`, `/Type0`, `/Subtype /Form`
  → headless form-fill generates **no appearance stream at all**.

### Why no AP (source-verified chain)
1. `PDFToolFormFill::execute` (pdftoolformfill.cpp) → `field->setValue(parameters)`
   with `parameters.modifier = &modifier` and `parameters.formManager =
   &formManager` (a plain core `pdf::PDFFormManager`).
2. `PDFFormFieldText::setValue` (pdfform.cpp:983):
   `builder->setFormFieldValue(getSelfReference(), parameters.value)` then
   `for (widget : getWidgets()) builder->updateAnnotationAppearanceStreams(
   formWidget.getWidget())`.
3. `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
   (pdfdocumentbuilder.cpp:1489): parses annotation, highlight special case,
   then per draw-key: `PDFContentStreamBuilder builder(mediaBox.size(), PDF
   coords)`; `parameters.formManager = m_formManager` (the BUILDER's member);
   `annotation->draw(parameters)` (:1533); `builder.end(...)`.
4. `PDFWidgetAnnotation::draw` (pdfannotation.cpp:3249): returns early if
   `!parameters.formManager`; for Text/Choice → `parameters.formManager->
   drawFormField(formField, parameters, false)`.
5. `PDFFormManager::drawFormField` (pdfform.cpp:914-919) is a **Q_UNUSED
   no-op** in core. Real drawing lives only in the optional GUI subclass
   `PDFWidgetFormManager` (Pdf4QtLibWidgets, uses `PDFTextEditPseudowidget::draw`,
   QPainter::drawText at pdftexteditpseudowidget.cpp:694/:748 — that is the tofu
   path the task brief described; headless never reaches it).
6. With no draw, `parameters.boundingRectangle` stays invalid → the loop
   `if (!parameters.boundingRectangle.isValid() || !contentStream.pageObject.
   isValid()) continue;` → `appearanceStreams` empty → no `/AP` merged.

Also note: pdftoolformfill.cpp never calls
`modifier.getBuilder()->setFormManager(&formManager)`, so the builder's
`m_formManager` is nullptr in the CLI path — another reason widget draw bails.
Verify before relying on `getFormFieldForWidget` inside
`updateAnnotationAppearanceStreams`; reading `/V` from the builder storage
directly avoids the dependency (the fresh `/V` is already merged before AP
generation runs, see step 2).

### Correction to a prior audit claim
`references/gui-text-input-rtl-audit.md` (and the SKILL.md §7 line) claim
`updateAnnotationAppearanceStreams` is "the one choke point that fixes form
fields AND FreeText at once" via `annotation->draw()`. For FORM FIELDS the
painter path is dead in headless core, so an RTL branch must generate the AP
DIRECTLY (bypassing `annotation->draw`), not swap the font inside it. FreeText
(WS-B's path, `PDFFreeTextAnnotation::draw` in pdfannotation.cpp) is a different
story — its draw is real in core.

## Proven RTL-embedding building blocks (from pdftooladdtext.cpp:181-423)

The CLI add-text RTL driver is the working reference pattern:
- `PDFRTLTextEngine::Settings { text, language (fa|ar|he|ur, '' = auto),
  fontSize, x, y, fontData (TTF bytes), fontFamily }`.
- `PDFRTLTextEngine::Result { fontDictionary, contentFragment, hasRTL, errors }`
  — `fontDictionary` is keyed by the passed `fontKey` (single entry);
  `contentFragment` is `BT ... ET` with `/<key> <size> Tf`, absolute `Tm`
  positioning, `/Span << /ActualText <hex> >> BDC` around RTL runs.
- Engine internals worth knowing: base direction = RTL only for
  fa/ar/he/ur; script = HB_SCRIPT_ARABIC for fa/ar/ur, HEBREW for he, else
  `hb_script_from_string("Arab")`; cluster_level = MONOTONE_CHARACTERS
  (marks get their own code); HarfBuzz ≥4 emits RTL runs leftmost-first, the
  engine does NOT reverse them (do not "fix").
- Embed: `builder->replaceObjectsByReferences(fontDictionary)` (turns nested
  FontFile2 stream etc. into real objects), compress fragment via
  `PDFFlateDecodeFilter::compress`, `PDFObject::createStream(dict, data)` with
  `Length` + `Filter [/FlateDecode]`, `builder->addObject(...)`.
- Font-key collision scan: page `/Resources` (may be an INDIRECT ref, e.g.
  `/Resources 29 0 R`) → `/Font` dict → pick first free `F<n>` (n from 2..64).
  Resolve through the object table, not the raw dict.

## RED test recipe (designed; fixture verified)

- Extend EXISTING `src/UnitTests/tst_formsignaturetest.cpp` with a private slot
  `test_formFillRtlAppearance` — no new file, no new CMake target
  (`UnitTestsFormSignature` exists, CMakeLists.txt:242-257).
- MUST add to that target in src/UnitTests/CMakeLists.txt:
  `target_compile_definitions(UnitTestsFormSignature PRIVATE
  TEST_FONT_ARABIC="${CMAKE_CURRENT_SOURCE_DIR}/../tests/fonts/NotoNaskhArabic-Regular.ttf")`
  (currently the target has NO compile defs).
- Slot body: runTool form-fill with `--field name --value 'سلام'`, assert exit 0
  + output exists; then byte-scan the output PDF for `/AP` and `/FontFile2`
  (embedded TTF subset) — FAILS at baseline (no AP at all). Optionally a
  `form-list` round-trip asserting the value `سلام` comes back (default text
  codec is utf8 — `getDefaultEncoding()` → "utf8", and the test runTool reads
  stdout as UTF-8).
- Field name in the embedded fixture: `name` (object 8, merged field+widget,
  `/T (name)`, `/Rect [100 700 300 720]`).

## Open decisions — RESOLUTION STATUS after WS-A continuation (2026-08-08)

1. **Font source — RESOLVED: (b) `--font` CLI option on form-fill.** The task
   brief explicitly chose this ("add --font option mirroring add-text"). CLI
   loads the TTF and passes the bytes into the builder via a new setter (e.g.
   `setFormFieldRtlFontData(QByteArray)` on PDFDocumentBuilder) so
   `updateAnnotationAppearanceStreams` can reach it; do NOT vendor a font into
   fonts.qrc and do NOT add compile defs to Pdf4QtLibCore (that was WS-B's
   rejected path). RED test passes `--font` → at baseline the option does not
   exist yet.
2. **RTL detection — undecided, design hint**: engine sets `hasRTL` per run;
   for form APs decide language (fa/ar/he/ur) — could sniff the first strong RTL
   char or default. Test value `سلام` is Arabic.
3. **Positioning — undecided, design hint**: x-origin should respect widget
   `/Rect` (+ quadding DA if present: `/DA (/Helv 0 Tf 0 g)` in the fixture —
   size 0 = auto).
4. Widget `/Rect` is available via `annotation->getRectangle()`; the generic AP
   loop's BBox = `parameters.boundingRectangle` (the annotation rect in PDF page
   coords) — an RTL branch should mirror that (BBox = widget rect, text in the
   same PDF coordinate space).

## RED implementation status (2026-08-08, WS-A continuation)

- **Committed: `e2efc315`** — `test(forms): RED — RTL form-fill AP must embed
  shaped font (M14)`. Contents: slot `test_formFillRtlAppearance` in
  tst_formsignaturetest.cpp (fills `name` with `سلام` + `--font
  <TEST_FONT_ARABIC>`, byte-scans for `/AP` + `/FontFile2`, form-list
  round-trip asserting `سلام`) + `TEST_FONT_ARABIC` compile def added to
  `UnitTestsFormSignature` in src/UnitTests/CMakeLists.txt (target had NO
  compile defs before). Pre-commit hook regenerated REPO_MAP.md — let it ride.
- **Verified failing at baseline**: `ctest -R UnitTestsFormSignature` →
  `FAIL! : test_formFillRtlAppearance() ... Actual (fillResult.exitCode): 1,
  Expected (0): 0` at tst_formsignaturetest.cpp:227; "6 passed, 1 failed;
  0% tests passed". NOTE the failure mode: **exit code 1, NOT the byte-scan** —
  because `QCommandLineParser::process()` (main.cpp:61) bails with
  `albdf: Unknown option 'font'.` on an unregistered option (it never reaches
  execute()). This is EXPECTED for a RED test exercising a not-yet-existing CLI
  option; do not "fix" it by dropping --font from the test.
- Build: `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg && cmake --build
  src/build -j8 --target UnitTestsFormSignature` (reconfigures automatically
  when CMakeLists.txt changed). Test run: `QT_QPA_PLATFORM=offscreen ctest
  --test-dir src/build -R UnitTestsFormSignature --output-on-failure`.
- GREEN not started (session hit tool budget after the RED commit).

## GREEN design (source-verified API map — IMPLEMENTED 2026-08-08)

Branch in `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
(pdfdocumentbuilder.cpp:1489), inserted AFTER the highlight block (:1505) and
BEFORE the pageDictionary lookup (:1507), guarding ONLY the form-field path:
`dynamic_cast<const PDFWidgetAnnotation*>(annotation.data())` (class at
pdfannotation.h:1288) — the FreeText branch is WS-B's, never touch it.

- Read `/V` from builder storage directly: `PDFDocumentDataLoaderDecorator
  loader(&m_storage)` + `loader.readString(widgetDict->get("V"))` (readString
  dereferences refs, pdfdocument.cpp:185-194). `/V` is already merged before AP
  gen runs (pdfform.cpp:997 then :1003).
- `PDFRTLTextEngine::create(settings, fontKey)` — fontKey "F2" (or a free
  F<N>); then `replaceObjectsByReferences(fontDictionary)` (builder.h:353),
  compress fragment via `PDFFlateDecodeFilter::compress`, build stream via
  `PDFObject::createStream(PDFStream(dict, data))` (pdfobject.h:263),
  `addObject` (builder.h:412), Form XObject dict via `mergeTo(formRef,
  formFactory.takeObject())` (builder.h:452) with
  `Type/XObject + Subtype/Form + BBox + Resources`, then
  `mergeTo(annotationReference, {/Rect, /AP << /N formRef >>})`.
- `PDFObjectFactory << QRectF` serializes as `[left, top, right, bottom]`
  (pdfdocumentbuilder.cpp:946-949) — valid BBox array.
- Widget rect: `annotation->getRectangle()` (pdfannotation.h:546).
- Builder members at pdfdocumentbuilder.h:1659-1661 (`m_storage`, `m_version`,
  `m_formManager`); `PDFDocumentModifier::getBuilder()` returns `&m_builder`
  (h:1673) — same builder instance the CLI holds.

## Commit plan (per task brief — ALL EXECUTED 2026-08-08: RED `e2efc315`, GREEN `21c42879`, docs `285deab9`)

1. RED: `test:` commit with the failing slot + CMake def (verify it fails).
   **DONE — `e2efc315` (see "RED implementation status" above).**
2. GREEN: `fix(core): RTL form-field appearance streams via PDFRTLTextEngine
   (M14)` — smallest change in pdfdocumentbuilder.cpp form-field branch only.
3. Update `docs/PROBLEMS.md` marking the form-field tofu gap resolved.
4. `python3 scripts/gen-repo-map.py` before committing (touched tracked files).
5. Git identity: `git -c user.name=yolka -c user.email=yolka@albdf.local`,
   `git commit --no-verify` allowed.
