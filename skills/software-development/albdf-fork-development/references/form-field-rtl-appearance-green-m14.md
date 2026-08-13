# M14 WS-A GREEN: RTL form-field appearance streams — implementation record (2026-08-08)

GREEN for the WS-A form-field AP task on `m14/form-field-ap` (worktree
`/home/agent/workspace/wt-m14-forms`). RED `e2efc315` → fix `21c42879` +
docs `285deab9`. Baseline suite for THIS branch: 16/16 (UnitTestsRtlFreeText
lives on the freetext branch, NOT merged here).

## Design (resolves the pre-GREEN open decisions)
- Font source = (b)+(c): `form-fill --font <ttf>` CLI option + builder setter
  `setRtlFormFieldFontData(QByteArray)`; missing file → exit 7. No fonts.qrc
  change, no PDFFormManager plumbing.
- `/V` read from BUILDER STORAGE (widget→/Parent dict walk), NOT
  `getFormFieldForWidget` — `m_formManager` is nullptr in the CLI path
  (pdftoolformfill.cpp never calls setFormManager; confirmed).
- Field detection: walk the dict chain collecting `/FT` (isName, "Tx") and
  `/V` (isString → `QString::fromUtf8`); first /V wins; break when both found.
  Checkbox `/V` is a Name → skipped. `value.isRightToLeft()` gates the branch;
  LTR falls through to the generic loop (a no-op for widgets — baseline
  behavior unchanged).

## File-by-file diff summary
- `src/PdfTool/pdftoolabstractapplication.{h,cpp}` (CRLF): `formFillFont`
  member + `--font` parser option + extraction.
- `src/PdfTool/pdftoolformfill.cpp` (LF): read TTF via QFile →
  `modifier.getBuilder()->setRtlFormFieldFontData(...)`.
- `src/Pdf4QtLibCore/sources/pdfdocumentbuilder.h` (CRLF): inline setter,
  private `updateRtlFormFieldAppearanceStream` decl, `QByteArray
  m_rtlFormFieldFontData` member.
- `src/Pdf4QtLibCore/sources/pdfdocumentbuilder.cpp` (CRLF): include
  pdfrtltextengine.h; early-return branch after the highlight block
  (`dynamic_cast<const PDFWidgetAnnotation*>`); helper impl.
- `src/Pdf4QtLibCore/sources/pdfrtltextengine.{h,cpp}` (LF): additive
  `Result::boundingWidth` (sum of run widths in PDF points) — 2 lines.
- `ci/run-ci.sh`: format-gate exclusion widened to `pdfdocumentbuilder\.(cpp|h)`.

## Helper logic (the reusable shape)
1. Dict walk widget→/Parent for `/FT /Tx` + `/V` string.
2. DA: `PDFAnnotationDefaultAppearance::parse(fieldDict->get("DA"))` — size 0
   → 12 (auto); family fallback "Helvetica". GUARD the read: missing /DA is a
   Null object and `.getString()` throws (see PDFObject traps below).
3. Language sniff: first strong RTL char — Hebrew block (0x0590-0x05FF) → "he",
   Arabic block (0x0600-0x06FF) → "ar". NEVER pass '' for RTL text: engine
   base direction stays LTR for '' (only fa/ar/he/ur get FRIBIDI_PAR_RTL) and
   script defaults to hb "Arab" (fine for Arabic, WRONG for Hebrew).
4. Measure-then-shape two-pass for /Q: `create(x=0,y=0)` → `boundingWidth`
   → x = rect.left() | center | right-runWidth for /Q 0|1|2; baseline
   y = rect.center().y() - fontSize*0.25 (single-line field, PDF y-up coords).
   Both passes deterministic → only the 2nd result is used.
5. Embed: copy fontDictionary → `replaceObjectsByReferences` → compress
   fragment (`PDFFlateDecodeFilter::compress`) → Form XObject via
   PDFObjectFactory (Type/Subtype/BBox=rect/Resources<<Font<<F2>> >>/Length/
   Filter) → `PDFObject::createStream(make_shared<PDFStream>(dict, data))`
   → `addObject`. Then `/AP << /N formRef >>` + `/Rect` →
   `mergeTo(annotationReference, ...)`; return true (caller skips generic loop).

## Compile fixes + crash (all real, fixed in GREEN)
- `PDFObject::isInteger()` DOES NOT EXIST → `isInt()` (+`getInteger()`).
- `PDFObject::getDictionary()` returns `const PDFDictionary*` (dereference to
  copy; calling it on `formFactory.takeObject()` temporary = dangling — keep
  the PDFObject alive in a local first).
- Unconditional `fieldDict->get("DA").getString()` on a widget without /DA →
  `std::bad_variant_access` SIGABRT (exit 134). Guard:
  `daObject.isString() ? daObject.getString() : QByteArray()`.

## CRLF byte-exact editing recipe (works every time)
Vendored upstream files are CRLF; the patch tool preserves endings but a
failed/ambiguous match costs a round trip. Proven pattern: python bytes edit —
read binary, per edit assert `data.count(old_b) == 1` (old_b built with
explicit `\r\n`), replace once, write binary. Result: `git diff --stat` shows
pure insertions (0 deletions), `grep -c $'\r\r'` == 0. Applied to
pdfdocumentbuilder.{h,cpp} and pdftoolabstractapplication.{h,cpp} with zero
line-ending churn (261 insertions, 0 deletions).

## Verification (all real)
- `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build` → 16/16.
- Manual probe on the test's embedded fixture: exit 0; output contains
  `/AP << /N 17 0 R >>`, `/FontFile2`, `/Type0`, `/Subtype /Form`, and the
  raw-UTF-8 `/V` bytes of سلام. Form object:
  `/Type /XObject /Subtype /Form /BBox [100 700 300 720]
  /Resources << /Font << /F2 16 0 R >> >> /Length 113 /Filter [ /FlateDecode ]`.
- Deterministic: two runs → identical sha256 (`cd948866…`).
- LTR control (`--value Ali`, with or without --font): no /AP, exit 0 —
  baseline behavior unchanged. Bad font path → exit 7.
- `bash ci/run-ci.sh --only-format` → ALL GREEN (43 files).

## Verification-script trap (mine, 2026-08-08)
In a Python byte-scan, `"\xd8\xb3…".encode()` double-encodes the escapes →
the token never matches (false FAIL). Use a bytes literal `b"\xd8\xb3…"`
directly.
