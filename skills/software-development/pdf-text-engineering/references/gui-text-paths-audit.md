# GUI text search/select/copy/extract paths — RTL reachability audit (2026-08-07, commit 9f5e1338)

Audit-only map (no modifications) of every GUI path where text is SEARCHED, SELECTED,
COPIED, or EXTRACTED in the vendored GUI layer (`ALBDF_BUILD_GUI=ON`), and whether our
RTL work (PDFTextSearchEngine + `/ActualText` ligature repair in PDFTextLayoutGenerator,
`pdftextlayoutgenerator.cpp:81-134`) reaches it. All line numbers verified against the
working tree; nothing fabricated.

## The one-paragraph answer

- **GUI search (both widgets) bypasses PDFTextSearchEngine entirely** — it calls
  `PDFTextLayoutStorage::find` → `PDFTextFlow::find` → `m_text.indexOf` (plain substring,
  no FriBidi visual inversion, no PDFRTLTextNormalizer, per-flow only so no cross-line).
  `PDFTextSearchEngine` is referenced ONLY by the CLI (`PdfTool/pdftoolsearchtext.cpp:74-99`)
  and unit tests — zero hits in `Pdf4QtLibGui`/`Pdf4QtLibWidgets`.
- **GUI selection/copy DOES get `/ActualText` repair for free**, because the layout is
  built by `PDFTextLayoutGenerator` (pdfcompiler.cpp:574-576), which applies the overlay
  via `m_textLayout.replaceCharacters(...)` at pdftextlayoutgenerator.cpp:132. Copied
  `لا`/`يي` are correct (but still visual order — no vis→log re-inversion).
- **OCR (PDFRecognizeText) bypasses the repair for its `info.text`** — text comes from raw
  `PDFEditedPageContentElementText` items (pdfrecognizetext.cpp:166-185), layout is used
  only for char boxes (:123-146). No GUI app instantiates it — CLI-only today.
- `PDFDocumentTextFlowEditorModel` is **core-only with no GUI instantiator in this tree**
  (it lives in `Pdf4QtLibCore/sources/pdfdocumenttextfloweditormodel.h`, NOT
  `Pdf4QtLibCore/PdfDocument/` — task-context path was wrong).

## Path table

| # | Path | file:line | Widget/Class | Mechanism | RTL-benefited today? |
|---|------|-----------|--------------|----------|----------------------|
| 1 | Advanced Find search + results | `Pdf4QtLibGui/pdfadvancedfindwidget.cpp:237-319` (find at :292 plain / :312 regex) | `PDFAdvancedFindWidget` | (b) `PDFTextLayoutStorage::find → PDFTextFlow::find → m_text.indexOf` | Partial — ligature repair yes; NO visual inversion / normalization / cross-line → logical-order Arabic never matches visual-order PDF text |
| 2 | Find-tool search + highlight | `Pdf4QtLibWidgets/sources/pdfwidgettool.cpp:571-631` (find at :610/:622), highlight :673-706, paint :354-368 | `PDFFindTextTool` | (b) same chain as #1; stores `pdf::PDFFindResults m_findResults` (pdfwidgettool.h:246), sorted at :625 | Partial — same as #1 |
| 3 | Select-text copy | `pdfwidgettool.cpp:867-895` (`onActionCopyText`, `getTextFromSelection` at :882) | `PDFSelectTextTool` | (c) `PDFTextLayout::getTextFromSelection` → `PDFTextFlow::getText` → `m_text.mid` (pdftextlayout.cpp:624-646, 1400-1413) | YES for ligatures (layout already repaired); copies in visual order (no vis2log) |
| 4 | Flow-editor text select | `Pdf4QtLibCore/sources/pdfdocumenttextfloweditormodel.h:73` → `.cpp:274-283` → `pdfdocumenttextflow.cpp:887-894` | `PDFDocumentTextFlowEditorModel` → `PDFDocumentTextFlowEditor` | (e) `item.text.contains(text, Qt::CaseSensitive)` per item | Partial — item strings built via generator (pdfdocumenttextflow.cpp:704-706) so repaired; NO inversion/normalization, case-sensitive, per-item only |
| 5 | OCR / recognize-text | No GUI path — CLI only (`PdfTool/pdftoolrecognizetext.cpp:80`; core `pdfrecognizetext.cpp:93-231`) | `PDFRecognizeText` (no widget) | (e) `PDFPageContentEditorProcessor` item chars (NOT layout) for text (:166-185); layout only for charBoxes (:123-146) | Bypassed for text — raw stream/ToUnicode chars, not repaired layout |
| 6 | Outline/bookmark search | `Pdf4QtLibGui/pdfsidebarwidget.cpp:877-890`, proxy :104-110, data `pdfitemmodels.cpp:389` | `PDFSidebarWidget` + `QSortFilterProxyModel` | (e) `setFilterFixedString`/`setFilterWildcard` → `QString::contains` on `getTitle()`, DisplayRole, CaseInsensitive | No (N/A page text) — raw outline titles from catalog |

## Confirmed call chains

**1/2 — search bypass (the core finding):**
```cpp
// pdfadvancedfindwidget.cpp:292 (and pdfwidgettool.cpp:610)
m_findResults = textLayoutStorage->find(expression, caseSensitivity, flowFlags);
```
```cpp
// pdftextlayout.cpp:1212-1224  PDFTextLayoutStorage::find
... PDFTextFlow::createTextFlows(textLayout, flowFlags, pageIndex);
    PDFFindResults flowResults = textFlow.find(text, caseSensitivity);
```
```cpp
// pdftextlayout.cpp:1353  THE actual matcher
int index = m_text.indexOf(text, 0, caseSensitivity);
```
Both widgets keep `PDFFindResults` (shape at `pdftextlayout.h:304-317`: `matched`,
`context`, `textSelectionItems`) and render via `.textSelectionItems` / `.matched` /
`.context` (pdfadvancedfindwidget.cpp:207-212,340; pdfwidgettool.cpp:687,701) — so any
adapter output in that shape drops in with zero downstream changes.

**3 — copy works:** `onActionCopyText` (pdfwidgettool.cpp:867) → permission check :872 →
`getTextLayoutLazy(pageIndex)` (:881) → `textLayout.getTextFromSelection(it, itEnd,
pageIndex)` (:882) → `PDFTextFlow::getText` → `m_text.mid` (pdftextlayout.cpp:1400-1413).
Layout produced by our generator (`pdfcompiler.cpp:574-576`); overlay applied at
`pdftextlayoutgenerator.cpp:132`. Same mechanism at pdfwidgettool.cpp:1935 (table extract).

**4 — flow editor:** `selectByContainedText` → `item.text.contains(text,
Qt::CaseSensitive)` (pdfdocumenttextflow.cpp:891); `item.text` originates from
`textFlow.getText()` over a generator-built layout (pdfdocumenttextflow.cpp:704-713).
Note: NO GUI app in-repo instantiates this model — latent core path.

**5 — no GUI OCR:** `grep PDFRecognizeText` in GUI dirs = zero hits. `recognize(page)`
builds `info.text` from `PDFEditedPageContentElementText::Item`s (raw stream chars,
:166-185), not from the repaired layout. The layout only supplies charBoxes (geometry
stays aligned).

**6 — outline search:** `onOutlineSearchText` → `m_outlineSortProxyTreeModel->
setFilterFixedString(text)` (pdfsidebarwidget.cpp:888); filter role DisplayRole, key
column 0, CaseInsensitive (:105-109); display = `outlineItem->getTitle()`
(pdfitemmodels.cpp:389).

## Why RTL still fails in GUI search (paths 1, 2, 4)

The engine (pdftextsearchengine.cpp:87-88) does `PDFRTLTextNormalizer::normalize` +
`invertToVisual()` (FriBidi `fribidi_log2vis`, :328-370), then line clustering + x-join +
word/soft-`\n` boundary mapping (:128-237) for CROSS-LINE phrase matching. GUI `indexOf`
does none of that, and `PDFTextFlow::find` runs per-flow under `SeparateBlocks` (both
widgets pass `PDFTextFlow::SeparateBlocks`), so even order-agnostic phrases spanning two
lines/blocks can never match.

## Minimal wiring (P0) — keep the PDFFindResult shape

One adapter in `Pdf4QtLibWidgets` serves both search widgets:

1. **Plain-text branch only** (regex/wildcard/whole-word stay on `storage->find`): per
   page, build `std::vector<PDFTextFlow>` from the existing storage
   (`storage.getTextLayout(page)` + `PDFTextFlow::createTextFlows(layout,
   SeparateBlocks|RemoveSoftHyphen, page)`), convert to `PDFDocumentTextFlow::Items`
   (text + `getBoundingBoxes()`, mirroring `pdfdocumenttextflow.cpp:709-714`), call
   `PDFTextSearchEngine::searchFlow(flow, query, first, last, options)` — it already does
   inversion + normalization + cross-line joining.
2. Map each `Match` → `PDFFindResult` (`matched = match.matchedText`; `textSelectionItems`
   from per-span `PDFCharacterPointer{page, block, line, char}` built by walking the
   flow's `m_characterPointers` — needs a tiny public accessor on `PDFTextFlow`, or reuse
   `getTextSelectionItems`; `context` = neighborhood).
3. Downstream (table rows, painter highlight, `goToPage`, `goToCurrentResult`) consumes
   `PDFFindResult` unchanged. `PDFTextSearchEngine` is `PDF4QTLIBCORESHARED_EXPORT` and
   LibWidgets already links LibCore privately (pdfwidgettool.cpp:882 proves core access
   from GUI).

`caseSensitive` maps to widget checkboxes; soft-hyphen flag maps to `RemoveSoftHyphen`.

## Prioritized fix list

- **P0 — GUI RTL phrase search non-functional (core differentiator absent from GUI):**
  swap the plain-text branch of `PDFFindTextTool::performSearch` (pdfwidgettool.cpp:571)
  and `PDFAdvancedFindWidget::performSearch` (pdfadvancedfindwidget.cpp:237) onto
  `PDFTextSearchEngine` + `Match→PDFFindResult` adapter.
- **P1 — extraction paths that still bypass repaired text:** `PDFRecognizeText::recognize`
  (pdfrecognizetext.cpp:166-185) should emit `info.text` from the repaired layout (bbox →
  `getTextFromSelection`) instead of raw stream-item chars, so recognize-text agrees with
  search and copy (delete-object index space stays unchanged).
- **P2 — latent/edge:** `selectByContainedText` (core, no GUI caller today) route through
  engine when a GUI consumer appears; `onActionCopyText` add FriBidi vis→log re-inversion
  for RTL clipboard; outline search normalize both sides via `PDFRTLTextNormalizer`.

## Key file locations (corrected/confirmed)

- `PDFDocumentTextFlowEditorModel`: `Pdf4QtLibCore/sources/pdfdocumenttextfloweditormodel.{h,cpp}`
  (NOT `Pdf4QtLibCore/PdfDocument/`).
- Engine: `Pdf4QtLibCore/sources/pdftextsearchengine.{h,cpp}` (exported, CLI+test only).
- `/ActualText` overlay: `Pdf4QtLibCore/sources/pdftextlayoutgenerator.cpp:81-134`.
- GUI layout build: `Pdf4QtLibWidgets/sources/pdfcompiler.cpp:442-444` (lazy) and
  :574-576 (background storage) — both via `PDFTextLayoutGenerator`.
