# M14 form-field AP recon — headless `form-fill` emits NO appearance stream

Date: 2026-08-08 · WS-A recon (agent hit tool cap before implementing; fix
dispatched to a continuation agent in the same worktree `wt-m14-forms`).
Status: recon verified; fix in flight (RED + GREEN commits pending).

## The empirical probe (stronger red than tofu)

```
albdf form-fill form.pdf filled.pdf --field name --value 'سلام'
```
- exit 0
- output PDF 1694 bytes
- contains `/V (\xD8\xB3\xD9\x84\xD8\xA7\xD9\x85)` (the logical value)
- **NO `/AP`, NO `/FontFile2`, NO `/Type0`, NO `/Subtype /Form`**

The headless field is INVISIBLE to viewers that render the AP — there is no
appearance at all, not merely a tofu one. Any RED test asserting
`/FontFile2` in the AP fails immediately at baseline for the right reason.

## Root cause chain (verified)

- `PDFFormFieldText::setValue` (pdfform.cpp:983) calls
  `builder->setFormFieldValue(...)` + `updateAnnotationAppearanceStreams(widget)`.
- `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
  (pdfdocumentbuilder.cpp:1489) parses the annotation and calls
  `annotation->draw(parameters)` (:1533).
- `PDFWidgetAnnotation::draw` (pdfannotation.cpp:3249) calls
  `PDFFormManager::drawFormField(...)`.
- **`PDFFormManager::drawFormField` (pdfform.cpp:914) is a `Q_UNUSED` NO-OP
  in core.** Real form-field drawing only exists in the optional GUI layer's
  `PDFWidgetFormManager` (Pdf4QtLibWidgets). Headless builds never generate a
  form-field AP.

So the choke point is the same `updateAnnotationAppearanceStreams` used by
FreeText (M14 sibling workstream) — but for form fields the QPainter path
never runs at all headlessly, so the RTL branch has to CREATE the AP from
scratch (via `PDFRTLTextEngine::create`), not just replace the font in an
existing drawn stream.

## Font-source decision (orchestrator, 2026-08-08)

Core `fonts.qrc` bundles only Liberation (Latin). There is NO Arabic font in
core resources. Options were: (a) vendor an OFL Arabic font into `fonts.qrc`,
(b) `--font <ttf>` CLI option on `form-fill` mirroring `add-text --font`,
(c) API seam passing fontData through PDFFormManager/builder.

**Decision: (b).** Keep core resource-free; `--font <ttf>` mirrors the
CLI-proven `add-text` pattern (pdftooladdtext.cpp:183-188: QFile read TTF
bytes, pass into the builder so the AP generator can embed). The RED test
passes `TEST_FONT_ARABIC` through the CLI. Rationale: smallest change, no
binary blob in the repo, consistent with the existing RTL write path.

## RTL branch design (for the continuation agent)

1. `pdftoolformfill.cpp`: add `--font <ttf>` (mirror add-text; QFile read).
2. In the form-field AP generation path (inside
   `updateAnnotationAppearanceStreams` form-field branch, or a helper it
   calls): when the field value is RTL —
   - read `/V` via `formManager->getFormFieldForWidget()` (pdftoolformfill
     already constructs `PDFFormManager` + `setFormManager` on the modifier
     builder, so the manager is available during AP generation);
   - `PDFAnnotationDefaultAppearance::parse(getDefaultAppearance())` →
     `getFontSize()` (fallback 12) and font family (fallback "Helvetica");
   - x/y origin from `annotation->getRectangle()` with quadding (field rect
     available via `annotation->getRectangle()`);
   - `PDFRTLTextEngine::create(settings, fontKey)` with
     `settings.text = logical value` (keep `/V` logical per spec),
     `fontData = --font TTF bytes`, `language = "ar"`;
   - `builder->replaceObjectsByReferences(fontDictionary)` (nested
     FontFile2/CIDToGIDMap streams become object refs);
   - compress `contentFragment` with `PDFFlateDecodeFilter::compress`;
   - `builder->addObject(stream)`; `mergeTo(widgetRef, apDict)`.
3. LTR and non-RTL values: unchanged (or minimal — the no-AP-at-all state is
   itself a pre-existing bug worth noting in PROBLEMS.md; the M14 scope is
   the RTL AP, don't expand to full LTR AP generation without orchestrator
   sign-off).

## RED test design

Extend `src/UnitTests/tst_formsignaturetest.cpp` (no new CMake target needed)
with slot `test_formFillRtlAppearance`:
- `runTool(form-fill m_formPdf filled.pdf --field name --value 'سلام' --font <TEST_FONT_ARABIC>)`
- read `filled.pdf` bytes; assert contains `/AP` and `/FontFile2` (or `/Type0`)
- `form-list` round-trip asserting output contains `سلام` (default codec utf8)
- add `TEST_FONT_ARABIC` compile def to `UnitTestsFormSignature` in
  `src/UnitTests/CMakeLists.txt` (line ~242 area; follow TEST_FONT_PERSIAN)
- fixture: embedded form PDF at tst_formsignaturetest.cpp:72, field name=`name`

Baseline: fails (no AP). After GREEN: passes.

## Baseline facts

- Suite 16/16 ctest green before changes.
- Worktree `wt-m14-forms` branch `m14/form-field-ap` based on `e667fe0a`.
- Build dir configured; 190/190 targets compile.
- No commits made by recon agent (tool cap); tree clean.
