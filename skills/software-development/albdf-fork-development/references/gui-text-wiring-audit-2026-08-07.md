# GUI ↔ core-library text wiring audit (albdf, 2026-08-07, verified by source inspection)

Report-only audit. **Supersedes `rtl-through-gui-integration.md` where they conflict**
(stale claims listed at the end). All file:line refs verified against branch `main`.

## Verdict: library-only (no PdfTool dependency) is correct

- `src/Pdf4QtLibGui/CMakeLists.txt:99` links `Pdf4QtLibCore Pdf4QtLibWidgets ...` — no
  PdfTool. The 3 GUI apps are thin `main.cpp` shells; CLI text commands are *consumers*
  of the same core classes. Never shell out to `albdf` from the GUI.
- All RTL text capabilities live in core: `PDFRTLTextEngine`, `PDFTextSearchEngine`,
  `PDFRTLTextNormalizer`, `PDFTextLayoutGenerator` (/ActualText overlay). No
  CLI-equivalent capability is missing at library level. The only gap is test-side:
  GUI apps have **no headless text-export flag**, so GUI text extraction can't be
  smoke-tested headlessly (fixture round-trips via `albdf fetch-text`).

## (1a) RTL add-text API

- `pdf::PDFRTLTextEngine::create(const Settings&, const QByteArray& fontKey)` —
  pdfrtltextengine.h:49-81. `Settings{text, language, fontSize, x, y, fontData(TTF
  bytes), fontFamily}`; `Result{fontDictionary, contentFragment (BT..ET visual order
  with `/Span << /ActualText <FEFF..> >> BDC`/`EMC` per RTL run), hasRTL, errors}`.
- CLI commit pattern (pdftooladdtext.cpp:200-537): pick a free `F<N>` key resolving
  page Resources through indirect refs (:217-268) → `create` (:269) →
  `builder->replaceObjectsByReferences(fontDictionary)` (:282) → Flate-compress
  `contentFragment` into a NEW stream object (:285-294) → merge font into page
  Resources keeping existing entries + append stream to /Contents (:299-537).
- **The CLI RTL path does NOT use `PDFPageContentEditorProcessor`** — only the LTR
  path does (:429-493). New GUI RTL text should mirror the RTL path (append a fresh
  stream) → sidesteps R#4 entirely. Editor-model integration (add
  `PDFEditedPageContentElementText` via `editedContent.addContentElement`, :481, then
  re-serialize through `PDFPageContentEditorContentStreamBuilder`, :485-494) triggers
  R#4 until the fix in §2 lands.
- GUI textbox tool is paint-only: `PDFPageContentElementTextBox`
  (pdfpagecontentelements.h:354) + `PDFCreatePCElementTextTool::finishEditing`
  (pdfpagecontenteditortools.cpp:787-798) → `m_scene->addElement(m_element->clone())`
  only. No document write. `PDFPageContentScene` (pdfpagecontentelements.h:544) is an
  overlay; the vendored GUI **never instantiates `PDFPageContentEditorProcessor`**
  (grep: only core + PdfTool use it) — so a GUI commit path must be built.

## (1b) RTL search

- `PDFTextSearchEngine` (pdftextsearchengine.h:50-102): `Match{pageIndex, itemIndex,
  matchedText, boundingRect, normalizedQueryIndex, spans}`; `Options{normalizer,
  caseSensitive}`; `search(document, query, pageFirst, pageLast, options)` and
  `searchFlow(flow, ...)` test seam. Normalizes + inverts query to visual
  (pdftextsearchengine.cpp:87-88), line-clusters + x-sorts (:132-164), soft line
  boundaries (:175+).
- GUI does NOT use it: `PDFAdvancedFindWidget::performSearch`
  (pdfadvancedfindwidget.cpp:292,312) and `PDFFindTextTool::performSearch`
  (pdfwidgettool.cpp:610,622) call `PDFTextLayoutStorage::find` →
  `PDFTextFlow::find` = plain `m_text.indexOf` (pdftextlayout.cpp:1349-1370). No
  inversion, no normalization, no cross-line matching.
- **Match → PDFFindResult mapping** (PDFFindResult is CORE: pdftextlayout.h:304-318
  `{matched, context, textSelectionItems}`; `PDFTextSelectionItems` =
  `vector<pair<PDFCharacterPointer, PDFCharacterPointer>>`, h:231-232):
  `matched` ← `match.matchedText`; `textSelectionItems` easiest via
  `PDFTextLayout::createTextSelection(pageIndex, boundingRect corners)`
  (h:449-453) — highlight/copy pipeline unchanged; `context` from page flow text
  around the rect. Keep regex/whole-words on the legacy path; route plain-text
  queries through `PDFTextSearchEngine::search`.

## (1c) Extraction / copy path

- Copy: `PDFSelectTextTool::onActionCopyText` (pdfwidgettool.cpp:867-895) →
  `PDFTextLayout::getTextFromSelection` (pdftextlayout.h:459-466) →
  `QApplication::clipboard()->setText` (:891). Layout comes from
  `PDFAsynchronousTextLayoutCompiler::getTextLayout` (pdfcompiler.cpp:442-444) using
  OUR `PDFTextLayoutGenerator`, whose `performMarkedContentBegin/End`
  (pdftextlayoutgenerator.cpp:81-134) applies the /ActualText overlay
  (`replaceCharacters` :132) — ligature repair works in GUI copy.
- Bug: the /ActualText payload is VISUAL order (built per glyph in
  pdfrtltextengine.cpp:415-434) → GUI copy of RTL yields a reversed string; needs
  `invertToVisual` at the copy boundary.

## (2) R#4 fix design (/ActualText dropped on content-stream rewrite)

Confirmed:
- Base `PDFPageContentProcessor` HAS `performMarkedContentPoint/Begin/End` virtuals
  (pdfpagecontentprocessor.h:674-682).
- `PDFPageContentEditorProcessor` overrides only 10 virtuals (h:251-260) — no
  marked-content override. TextBegin/End in `performInterceptInstruction`
  (cpp:65-98); sequences in `performProcessTextSequence` (cpp:137-149); gfx-state
  items in `performUpdateGraphicsState` (cpp:123-135).
- `PDFPageContentEditorContentStreamBuilder::writeEditedElement`
  (pdfpagecontenteditorcontentstreambuilder.cpp:538-646): text →
  `getItemsAsText()` XML (:598) → `writeText` (:637) → QXmlStreamReader round trip
  (:814-838, `writeTextCommand` :864+). **Zero BDC/EMC/ActualText anywhere in the
  file.**
- `PDFEditedPageContentElementText::Item` struct: pdfpagecontenteditorprocessor.h:150-157.

Design (chosen: capture-and-reemit on the EXISTING Text element — no 4th type):
1. Add `performMarkedContentBegin/End` overrides to the processor; on tag `Span`
   with an `/ActualText` string property (same check as
   pdftextlayoutgenerator.cpp:91-101 incl. the `isString()` guard), record a mark at
   current `m_contentElementText->getItems().size()` with the decoded text
   (`PDFEncoding::convertTextString`); a small stack handles nesting; pop on End.
2. Extend `Item` with optional `QByteArray actualText` (UTF-16BE + BOM, as the
   engine builds it at pdfrtltextengine.cpp:425-431); mark-begin item carries it,
   end is implicit at next mark-begin / vector end.
3. In `writeText`, emit `/Span << /ActualText <...> >> BDC` after the BT/Tf/Tm block
   (around :780-812) and `EMC` before `ET Q` (:861) — per-element wrap matches the
   engine's per-run scoping.
Rejected: 4th `Type::MarkedContent` element — ripples through writeEditedElement's
asText/asPath/asImage dispatch (:569-640) and `PDFPageContentElementEdited::drawPage`
(pdfpagecontentelements.cpp:2689-2771), which has no use for a bare mark.
Both files upstream-derived → add to the `ci/run-ci.sh` format-gate exclusion list.
Verification recipe: `add-text --rtl` fixture → second `add-text` (LTR) on the same
page → `fetch-text`: pre-fix degrades lam-alef (`لا`→`ل`), post-fix identical. Same
regression a GUI content-editor commit would hit.

## (3) Other GUI text gaps (checklist)

1. GUI search bypasses `PDFTextSearchEngine` — no RTL inversion, no tashkeel/ZWNJ
   normalization, no lam-alef/presentation-form folding, no cross-line phrases.
2. No RTL toggle / direction awareness in the textbox tool
   (PDFCreatePCElementTextTool, pdfpagecontenteditortools.cpp:669-798); no path from
   typed text to `PDFRTLTextEngine::create`.
3. Font selection is a plain `QFontComboBox` (pdfpagecontenteditorstylesettings.cpp:71,
   222-231; QFontDialog :404-411) — no TTF-file picker, no `language` field, no
   embedded-font awareness.
4. RTL copy yields visual-order text (see 1c).
5. Paste is passive: `PDFTextEditPseudowidget::performPaste`
   (pdftexteditpseudowidget.cpp:485-489) — raw clipboard text, no shaping until a
   commit path exists.
6. Legacy `find` is per-flow only — a phrase straddling flows/line breaks can't
   match (pdftextlayout.cpp:1212-1240).
7. `PDFDocumentTextFlowEditorModel::selectByContainedText`
   (pdfdocumenttextfloweditormodel.h:73) — plain regex, no normalization/inversion.
8. TTS speech page compiled out (commit 48d58fd8, `isValid()==false` stub) — dead by
   design; do not re-add Qt6::TextToSpeech.

## Stale claims in `rtl-through-gui-integration.md` (do not re-cite)

- It says the GUI dirs are "NOT wired into the build" — superseded: GUI builds green
  (commit 7b497852, `ALBDF_BUILD_GUI=ON`, all 5 targets, gui-smoke passes).
- It cites pdfpagecontentelements.cpp:2654 as the textbox commit hook — the real
  verified hook is `PDFCreatePCElementTextTool::finishEditing`
  (pdfpagecontenteditortools.cpp:787-798); the textbox element has no commit method.
