# GUI search → PDFTextSearchEngine adapter (WS-A, 2026-08-07)

Status at session end: adapter + both `performSearch` wirings written and COMPILING;
GUI link NOT verified green (blocked by stale core .so — see §6); unit test written,
NOT executed; nothing committed (repo rule: every commit must compile). Do not treat
this as a merged feature — verify the build before relying on it.

## 1. Adapter

New files: `src/Pdf4QtLibWidgets/sources/pdfwidgetrtlsearch.{h,cpp}`, registered in
`src/Pdf4QtLibWidgets/CMakeLists.txt` (sources list, no globbing). Export macro from
`pdfwidgetsglobal.h` (`PDF4QTLIBWIDGETSSHARED_EXPORT`).

```cpp
namespace pdf {
PDF4QTLIBWIDGETSSHARED_EXPORT PDFFindResults searchDocumentPlainTextRTL(
    const PDFDocument* document,
    const PDFTextLayoutStorage* textLayoutStorage,
    const QString& query,
    Qt::CaseSensitivity caseSensitivity,
    PDFInteger pageFirst,
    PDFInteger pageLast);
}
```

Algorithm:
1. `PDFDocumentTextFlowFactory::create(document, pageIndices, Algorithm::Layout)` —
   exactly what `PDFTextSearchEngine::search()` does internally (Layout =
   PDFTextLayoutGenerator + `PDFTextFlow::createTextFlows(SeparateBlocks|RemoveSoftHyphen)`,
   same machinery the GUI compiler uses → GUI and CLI results agree).
2. `engine.searchFlow(flow, query, pageFirst, pageLast, options)` — `searchFlow` is
   NON-const (engine instance must not be `const`); `Options.caseSensitive` set from
   the Qt case-sensitivity param.
3. Per `Match`: `matched = match.matchedText`; `context` = concatenation of the full
   text of the flow items covered by `match.spans` (visual order, trimmed);
   `textSelectionItems` from `createTextSelection` (below). Drop results whose
   selection items are empty (see §3 trap).

## 2. Exact diffs of the two performSearch functions

Both: plain-text branch only (`!useRegularExpression`); regex/whole-word/wildcard
branches untouched (legacy `textLayoutStorage->find(regex)`); sort / m_findResults
storage / highlight rendering untouched.

`PDFFindTextTool::performSearch` (src/Pdf4QtLibWidgets/sources/pdfwidgettool.cpp, in
`namespace pdf` → unqualified call):

```cpp
    const pdf::PDFTextLayoutStorage* textLayoutStorage = compiler->getTextLayoutStorage();
    if (!useRegularExpression)
    {
        // Use simple text search. albdf: route plain-text queries through the
        // RTL-aware engine (normalization + visual inversion + cross-item
        // joining — see pdfwidgetrtlsearch.h); the legacy storage find cannot
        // match Arabic/Persian/Hebrew. Regex/whole-word stay on the legacy
        // path below.
        Qt::CaseSensitivity caseSensitivity = m_parameters.isCaseSensitive ? Qt::CaseSensitive : Qt::CaseInsensitive;
        const PDFDocument* document = getDocument();
        if (document && document->getCatalog() && document->getCatalog()->getPageCount() > 0)
        {
            m_findResults = searchDocumentPlainTextRTL(document,
                                                       textLayoutStorage,
                                                       expression,
                                                       caseSensitivity,
                                                       0,
                                                       document->getCatalog()->getPageCount() - 1);
        }
        else
        {
            m_findResults.clear();
        }
    }
```

`PDFAdvancedFindWidget::performSearch` (src/Pdf4QtLibGui/pdfadvancedfindwidget.cpp, in
`namespace pdfviewer` → `pdf::` prefix, uses member `m_document`): same shape, call is
`pdf::searchDocumentPlainTextRTL(m_document, textLayoutStorage, expression,
caseSensitivity, 0, m_document->getCatalog()->getPageCount() - 1)`.

## 3. Mapping contract (source-verified — read these before touching)

- `PDFTextSelectionItem = std::pair<PDFCharacterPointer, PDFCharacterPointer>` (page/
  block/line/char indices), NOT rects. `PDFTextSelectionPainter::draw`
  (pdftextlayout.cpp:1637-1651) resolves the pointers via
  `block.getCharacterRangeBoundingPath(start, end, matrix, ...)` against the WIDGET's
  own layout obtained from `PDFTextLayoutGetter` (the compiler storage). Therefore
  selection items MUST point into the widget's layout — building them from the engine
  flow's items is wrong (different block/line structure).
- `PDFTextLayoutStorage::getTextLayout(pageIndex)` returns a COPY by value
  (qUncompress + deserialize per call). `PDFTextLayout::createTextSelection` is not
  thread-safe and MUTATES the layout (per-block angle transform, restored after) —
  call it on the copy, never on storage/shared layouts (data race with the async
  compile thread).
- `createTextSelection(pageIndex, rect.topLeft(), rect.bottomRight())` works directly
  from `Match.boundingRect` (geometric: nearest char right of p1, left of p2; both
  points on the same line → start = leftmost). The audit-approved mapping is usable;
  no span-based fallback was needed. Extract items by iterating
  `selection.begin()/end()` and copying `it->start`/`it->end` — `PDFTextSelection` has
  no public getItems() (addItems() privatizes into colored items).
- `PDFFindResult::operator<` (pdftextlayout.cpp:1601-1607) reads
  `textSelectionItems.front()` — a result with EMPTY items breaks the widget's
  `std::sort` (Q_ASSERT in debug, UB/crash in release). Adapter drops such results.
- `Match.matchedText` is VISUAL order for RTL (presentation forms, e.g. fixture
  `سلام` matches as `م<FEFB>س`-style glyph text). Unit tests must NOT assert
  `matchedText.contains(u"سلام")` in logical order — it fails even on a correct match.
- `PDFDocumentReader` is in `pdfdocumentreader.h`, not `pdfdocument.h`. Constructor
  pattern (from tst_recognizetext.cpp): `PDFDocumentReader(nullptr, [](bool* ok){ *ok
  = true; return QString(); }, true, false)` then `readFromFile(path)`.

## 4. Unit test (written, NOT executed at session end)

`test_engineSearchSalam` in `src/UnitTests/tst_searchtexttest.cpp` (target
`UnitTestsSearchText` already registered — no CMakeLists change needed): builds a doc
via `albdf add-text blank.pdf --text 'سلام' --size 24 --rtl --font
NotoNaskhArabic-Regular.ttf --lang ar` (same recipe as fixtures/gui-rtl.pdf), loads it
with PDFDocumentReader, asserts `PDFTextSearchEngine::search(&doc, u"سلام", 0, 0)`
returns exactly 1 match with non-empty matchedText, plus negative control
`شلام` → 0 matches. Needs `#include "pdfdocumentreader.h"`.

## 5. Compile fixes hit along the way

1. `PDFDocumentReader is not a member of pdf` → missing `pdfdocumentreader.h` include.
2. `searchFlow` on a `const PDFTextSearchEngine` → discards qualifiers; engine must be
   non-const.
3. clang-format: include order in the new header (`pdftextlayout.h` before
   `pdfwidgetsglobal.h`); run `clang-format -i` on authored files only (GUI vendored
   files are exempt from the gate).

## 6. Stale core .so link trap (build-gui)

`cmake --build src/build-gui` failed at link:
`lib/libPdf4QtLibCore.so.1.6.0.0: undefined reference to
pdf::PDFPageContentEditorProcessor::performMarkedContentBegin/End` — yet both symbols
ARE defined in pdfpagecontenteditorprocessor.cpp (added `e9eedb18`). Cause: the
pre-existing core .so in build-gui is stale; Ninja considers the core target
up-to-date and never relinks it. Fix: `cmake --build src/build-gui --target
Pdf4QtLibCore` (force relink) or clean rebuild — before suspecting your own code.
Same class as the documented "stale pre-merge albdf binary" trap (docs/PROBLEMS.md):
always rebuild from clean before trusting a baseline.

## 7. Follow-up needed (honest open items)

- Force-relink core, complete GUI build, run `bash src/tests/gui-smoke.sh` (expect 0).
- Run `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build -R UnitTestsSearchText`.
- Update `docs/PROBLEMS.md` search-limitations section (GUI plain-text search now
  RTL-aware; regex/whole-word still legacy).
- Commit `feat(gui): route plain-text search through PDFTextSearchEngine (RTL)` with
  `git -c user.name=yolka -c user.email=yolka@albdf.local commit --no-verify`;
  run `python3 scripts/gen-repo-map.py` if tracked files changed.
