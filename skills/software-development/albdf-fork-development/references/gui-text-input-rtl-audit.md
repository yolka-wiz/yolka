# GUI text-input → RTL audit (albdf, main @ 9f5e1338, 2026-08-07)

AUDIT ONLY (no code changed). Maps every GUI path where a user types/pastes text
that can become document content, and states the RTL situation + minimal fix per
path. **Headline: no GUI path uses `PDFRTLTextEngine` today.** All commit-visible
text paths are raw `QLineEdit`/`QTextEdit`/`QPainter::drawText`/`QTextLayout`.

## Choke point that fixes most paths at once

All annotation + form-field appearance streams regenerate through:

- `PDFDocumentBuilder::updateAnnotationAppearanceStreams` — `src/Pdf4QtLibCore/sources/pdfdocumentbuilder.cpp:1489-1575`: parses the annotation, then `annotation->draw(parameters)` with a `PDFContentStreamBuilder` painter (line 1531-1534).
- The `QPainter::drawText(...)` calls inside annotation `draw()` implementations become the PDF text operators of the AP stream.

A single RTL branch here (when the text is Arabic/Persian/Hebrew, emit a
`PDFRTLTextEngine::create` Type0 font + shaped fragment instead of the painted
QTextLayout) fixes form fields AND FreeText at once. `/V` and `/Contents` stay
logical Unicode strings (spec-correct); only the AP needs shaping.

## Path table

| Path | file:line | Commits to doc? | RTL today | Minimal fix |
|---|---|---|---|---|
| Canvas textbox tool `PDFCreatePCElementTextTool` → `PDFPageContentElementTextBox` + `PDFTextEditPseudowidget` | `Pdf4QtLibWidgets/sources/pdfpagecontenteditortools.cpp:669-691` (tool ctor), `:778-782` (appearance), `:787-798` (`finishEditing` → `m_element->setText(...)` → `m_scene->addElement`) | **NO** — scene is screen-only; no serializer writes scene elements to a content stream anywhere in the vendored GUI | Bidi yes (QTextLayout + `QPainter::drawText` at `pdfpagecontentelements.cpp:2567, 2619`); no HarfBuzz | When/if a scene→stream serializer lands, emit via `PDFRTLTextEngine`; until then screen-only = low risk |
| Pseudowidget inline edit `PDFTextEditPseudowidget` | `pdftexteditpseudowidget.{h,cpp}` — ctor :35-44, `keyPressEvent` :96-330, `performPaste` :484-489, `performInsertText` :553-565, `draw` :748 (`m_textLayout.draw`), comb drawText :694, `updateTextLayout` :818-877 | Only via owning editors (fields / textbox tool) | `QTextLayout` bidi-aware (logical edit + visual reorder; Key_Direction_L/R handled :282-295); **no HarfBuzz → Arabic never joins while typing** | HarfBuzz-shape RTL display runs in `updateTextLayout`/`draw`; or accept Qt display, shape only at AP/commit time |
| Content-editor text item edit `PDFPageContentEditorEditedItemSettings` (`QPlainTextEdit`) | `pdfpagecontenteditorediteditemsettings.cpp:109-114` (load `getItemsAsText`), `:253-256` (`textElement->setItemsAsText(ui->plainTextEdit->toPlainText())`) | **Partial/broken** — changes only `m_itemsAsText`; glyph path `m_textPath` is NOT regenerated (`pdfpagecontentelements.cpp:2765-2770` fills the pre-parsed `getTextPath()`), so doc stream is untouched by the dialog | Bidi yes (QPlainTextEdit); stored string is logical so no shaping needed for the string itself | Re-run page-content editor processor over the new text to rebuild items + textPath, or disable the text tab for text items (stale-glyph trap) |
| Form field text `PDFFormFieldTextBoxEditor` / `PDFFormFieldComboBoxEditor` (via `PDFTextEditPseudowidget`) | `pdfwidgetformmanager.cpp` — `initializeTextEdit` :1611-1632 / :1552-1565; **commit** `setFocusImpl` :1634-1657 and :1576-1599: `PDFObjectFactory::createTextString(m_textEdit.getText())` → `m_formManager->setFormFieldValue(...)` | **YES** — `/V` string + AP regenerated via `updateAnnotationAppearanceStreams` | `/V` logical (spec-OK); AP drawn with DA font (base-14 → tofu for Arabic) | AP-level: for RTL values build AP via `PDFRTLTextEngine::create` inside `updateAnnotationAppearanceStreams`; keep `/V` logical; optionally normalize input via `PDFRTLTextNormalizer` |
| Sticky note `PDFCreateStickyNoteTool` — `QInputDialog::getText` | `pdfadvancedtools.cpp:99`, commit :107 `createAnnotationText(...)` | **YES** — `/Contents` string | Bidi yes (QLineEdit); stored text is logical | P2: single-line QLineEdit blocks multi-line Arabic paste → `QInputDialog::getMultiLineText` |
| FreeText annotation `PDFCreateFreeTextTool` (`QTextEdit` dialog) | `pdfadvancedtools.cpp:374` (widget), `:442` (`text = textEdit->toPlainText()`), `:464` (`createAnnotationFreeText`); core AP: `pdfdocumentbuilder.cpp:3419, :3574`; draw: `pdfannotation.cpp:2815` `painter->drawText(QRectF(QPointF(0,0), textRect.size()), getContents(), option)` | **YES** — `/Contents` (logical) + regenerated `/AP` drawn with DA font (base-14 → **no Arabic glyphs, tofu**) | Bidi yes (QTextEdit + QPainter::drawText); **AP gets no shaping** | **P0**: in `PDFFreeTextAnnotation::draw` AP path, when contents is RTL emit appearance via `PDFRTLTextEngine::create` (embedded font + shaped run), keep `/Contents` logical |
| Stamp `PDFCreateStampTool` | `pdfadvancedtools.cpp:1167-1265` (`setStamp(Stamp)` :1254, commit :1264) | **YES** — but only PRESET stamps, no free-text input | n/a | None (no user text) |
| Raw annotation edit `PDFEditObjectDialog`/`PDFObjectEditorWidget` ("Edit" on annotation) | `pdfwidgetannotation.cpp:1191-1214` (`onEditAnnotation` → `builder->setObject` :1205 + `updateAnnotationAppearanceStreams` :1206); model `pdfobjecteditormodel.cpp:488-820` | **YES** — replaces annotation object verbatim + AP | None (expert raw-PDF path) | P2: no shaping needed; semantic strings |
| Find dialog `searchPhraseEdit` (QLineEdit) | `pdfadvancedfindwidget.cpp:50` (connect returnPressed), `:292,:312` (`performSearch`); .ui:69 | **NO** — screen-only search | **NOT RTL-correct (CORRECTED 2026-08-07, source-verified):** calls the legacy `PDFTextLayoutStorage::find` → `PDFTextFlow::find` = plain `m_text.indexOf` (`pdftextlayout.cpp:1353`) — no FriBidi inversion, no tashkeel normalization, no cross-line; `PDFTextSearchEngine` is referenced in NO GUI file. Same for `PDFFindTextTool::performSearch` (pdfwidgettool.cpp:610,622) | Route plain queries through `PDFTextSearchEngine::search` + map `Match` → `PDFFindResult` (mapping design: `references/gui-text-wiring-audit-2026-08-07.md` §1b); keep regex/whole-words on the legacy path |
| Sidebar search filters `outlineSearchLineEdit`, `notesSearchLineEdit` | `pdfsidebarwidget.cpp:113-114, :178-179`; .ui:382, 572 | **NO** — UI list filters | Bidi yes | None |
| Viewer settings `cmsProfileDirectoryEdit`, `backgroundColorEdit`, `foregroundColorEdit` | `pdfviewersettingsdialog.ui:693, 763, 780` | **NO** — app settings | Bidi yes | None |
| Document metadata — XMP `QPlainTextEdit`; Info-dict fields read-only | `pdfdocumentpropertiesdialog.cpp:127-131` (read-only Title/Subject/Author/Keywords/Creator), `:591-614` (`xmpMetadataPlainTextEdit->setPlainText(...)`), `:743-746` (`getXMPMetadata() = ...toPlainText().toUtf8()`); commit `pdfprogramcontroller.cpp:1386-1399` (`builder->setCatalogMetadata(...)`) | **YES** — catalog metadata stream (UTF-8 XML; no glyph shaping concept — safe for RTL as XML text) | Bidi yes; XML `xml:lang="x-default"` only | P2: `xml:lang` per title alt (ar/fa/he) |

## Other verified facts

- `PDFPageContentElementEdited::drawPage` renders text by filling the parsed
  `getTextPath()` (`pdfpagecontentelements.cpp:2765-2770`) — so existing RTL PDFs
  (e.g. CLI `add-text --rtl` output) DISPLAY correctly in the GUI; only new GUI
  input is unshaped.
- `PDFEditedPageContentElementText` model is shared with the CLI
  (`pdftooladdtext.cpp:432-481`) — CLI RTL pipeline is separate and working.
- Popup for markup-annotation comments is a read-only `QLabel` with
  `Qt::TextBrowserInteraction` (`pdfwidgetannotation.cpp:1307-1313`).
- No consumer of `PDFPageContentScene` → content stream was found in
  Pdf4QtLibGui/Pdf4QtEditor (searched `PDFPageContentEditorWidget`,
  `PDFCreatePCElement...`; only `PDFCreateFreeTextTool` appears, at
  `pdfprogramcontroller.cpp:1127`). "Commits-to-doc = NO" for the scene rests on
  absence of evidence in inspected files.
- `PDFListBoxPseudowidget` (combo/listbox popup) not read in detail; shares the
  same QTextLayout-only display path.

## Priority list (from the audit)

- **P0** (user types → saved PDF shows tofu/broken): form-field APs via
  `updateAnnotationAppearanceStreams` + `PDFTextEditPseudowidget::draw`;
  FreeText AP (`pdfannotation.cpp:2713-2816` + `createAnnotationFreeText`);
  content-editor text-item edit staleness (`pdfpagecontenteditorediteditemsettings.cpp:253-256`).
- **P1**: pseudowidget display shaping (`pdftexteditpseudowidget.cpp:818-877`);
  scene→stream serializer for the canvas textbox (`pdfpagecontenteditortools.cpp:787-798`);
  input normalization via `PDFRTLTextNormalizer` on field/FreeText commit.
- **P2**: `/ActualText` overlay + `xml:lang` in XMP titles
  (`pdfdocumentpropertiesdialog.cpp:632-647`); sticky-note multi-line input;
  RTL alignment in raw object editor.
