# M14 WS-A: RTL form-field appearance streams — session record (2026-08-08)

Session: delegated WS-A task on `m14/form-field-ap` (worktree
`/home/agent/workspace/wt-m14-forms`, base `origin/main e667fe0a`). The session
hit its tool budget BEFORE implementing GREEN — everything below is VERIFIED
(source reads + real builds/runs) up to the point stated; the GREEN design is a
plan, not a tested result.

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

## Open decisions (session ended before GREEN)

1. **Font source**: core `fonts.qrc` bundles only Liberation (Latin) — no Arabic
   font in core. Options: (a) vendor an OFL Arabic font into fonts.qrc,
   (b) add `--font` option to form-fill CLI mirroring add-text, (c) plumb
   fontData through the builder/form manager. The RED test only needs the CLI to
   accept a font; the manual CLI recipe in the task brief wants
   `form-fill ... --value 'سلام'` to embed the font, which implies (b) or (a).
2. **RTL detection**: engine sets `hasRTL` per run; for form APs decide
   language (fa/ar/he/ur) — could sniff the first strong RTL char or default.
3. **Positioning**: x-origin should respect widget `/Rect` (+ quadding DA if
   present: `/DA (/Helv 0 Tf 0 g)` in the fixture — size 0 = auto).
4. Widget `/Rect` is available via `annotation->getRectangle()`; the generic AP
   loop's BBox = `parameters.boundingRectangle` (the annotation rect in PDF page
   coords) — an RTL branch should mirror that (BBox = widget rect, text in the
   same PDF coordinate space).

## Commit plan (per task brief, NOT executed)

1. RED: `test:` commit with the failing slot + CMake def (verify it fails).
2. GREEN: `fix(core): RTL form-field appearance streams via PDFRTLTextEngine
   (M14)` — smallest change in pdfdocumentbuilder.cpp form-field branch only.
3. Update `docs/PROBLEMS.md` marking the form-field tofu gap resolved.
4. `python3 scripts/gen-repo-map.py` before committing (touched tracked files).
5. Git identity: `git -c user.name=yolka -c user.email=yolka@albdf.local`,
   `git commit --no-verify` allowed.
