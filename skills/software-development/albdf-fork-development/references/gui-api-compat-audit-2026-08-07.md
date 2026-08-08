# GUI ↔ modified-core API compatibility audit (2026-08-07, analysis-only, verified)

Question: do the vendored GUI layers (from upstream tag v1.6.0.0) compile against our
MODIFIED core (`src/Pdf4QtLibCore`, fork base `6bf5047`)? Answer: **YES — compiles**.
Every changed/added core API is additive or signature-identical; 4 behavioral deltas exist.

## 0. Baseline verification first (do this before trusting any diff)

In this repo, `git diff 6bf5047 v1.6.0.0 -- <file>` shows THOUSANDS of phantom lines
(e.g. 1214 for pdftextlayout.h) — pure CRLF-vs-LF noise, not content. The fork base IS
upstream v1.6.0.0 content (different SHAs, divergent history, same tree). Always compare
content across commit boundaries with whitespace ignored:

```bash
git show 6bf5047:src/Pdf4QtLibCore/sources/pdftextlayout.h > /tmp/a.h
git show v1.6.0.0:Pdf4QtLibCore/sources/pdftextlayout.h > /tmp/b.h
diff -w -B /tmp/a.h /tmp/b.h | wc -l   # 0 = identical content
```

Same check for vendored GUI vs the tag (`Pdf4QtLibWidgets/sources/pdfwidgettool.cpp` etc.):
0 lines — the vendored GUI differs from upstream only in swapped license headers.
Exception: `pdfutils.h` has ONE real pre-existing delta (fork has the older
`PDFIntegerRange::Iterator` superset impl) — benign, GUI uses range-for only.

## 1. Header classification (git diff 6bf5047 HEAD -- src/Pdf4QtLibCore/sources/<h>)

| Header | Class | Notes |
|---|---|---|
| pdftextlayout.h | ADDITIVE + pure reformat | added `getCharacterCount()`, `replaceCharacters(index,count,QString)`; every existing decl re-emitted identically |
| pdftextlayoutgenerator.h | ADDITIVE + reformat | 2 protected overrides (`performMarkedContentBegin/End`) + `ActualTextSpan` member; 8-arg ctor untouched |
| pdfutils.h | UNMODIFIED | only pdfutils.cpp changed |
| pdfrecognizetext.h / pdftextsearchengine.h / pdfrtltextengine.h / pdfrtltextnormalizer.h | NEW files (no upstream counterpart) | GUI cannot reference them; trivially safe |

`git diff -w` still lists reformatted one-liners as -/+ pairs; before claiming a REMOVAL,
grep the HEAD header for each removed-looking signature (e.g. `getTextFromSelection`,
`selectLineInBlock`, `getTextLayoutLazy`) — all must still resolve.

## 2. Per-API verdicts (GUI call sites quoted)

- `PDFClosedIntervalSet::parse(first,last,text,&err)` — compiles (signature unchanged);
  **behavioral**: upstream ACCEPTED out-of-range values (no clamp — `addInterval` is a bare
  emplace+normalize), ours returns error + empty set. GUI: `Pdf4QtLibWidgets/sources/
  pdfselectpagesdialog.cpp:105` (`.unfold()` ignoring the error) and `:125` (`accept()`
  gates `QMessageBox::critical`) → dialog now REJECTS e.g. "1-100" on a 20-page doc.
- `PDFTextLayout*` methods (getTextBlocks/getCharacters/getTextFromSelection/
  isHoveringOverTextBlock/createTextSelection) — all signatures preserved; GUI call sites
  `pdfcompiler.cpp:487,496,508`, `pdfdrawspacecontroller.cpp:869,892`,
  `pdfwidgettool.cpp:802,882,1935,2078`, `pdfadvancedtools.cpp:1407,1677`. Semantics
  unchanged (pdftextlayout.cpp = formatting + additive only).
- `PDFTextLayoutGenerator` 8-arg ctor + processContents/createTextLayout — matches GUI
  call sites `pdfcompiler.cpp:442,574` exactly. **Behavioral (intended)**: new BDC/EMC
  overrides apply /ActualText repair; only affects docs with /ActualText marked content
  (our RTL-written docs, tagged PDFs). GUI-visible via copy/search/selection text.
- `PDFDocumentBuilder` (header untouched, .cpp modified) — GUI uses it in
  `pdfprogramcontroller.cpp:1390,1474,1658`, `pdfsidebarwidget.cpp:1449`,
  `pdfwidgetannotation.cpp:110,404,...`, `pdfobjecteditorwidget.cpp:988`.
  **Behavioral**: CreationDate/ModDate = fixed epoch (1970-01-01Z) or SOURCE_DATE_EPOCH.
- `PDFPageContentEditorProcessor`/`ContentStreamBuilder` (.cpp only) — GUI reaches them via
  unchanged `PDFPageContentEditor` facade (pdfpagecontenteditorwidget.cpp). **Behavioral**:
  XML round-trip sanitizes C0 control chars → U+FFFD, reals serialized FixedNotation/prec 8
  (both ends changed consistently → round-trip works).

## 3. Qt modules beyond Core/Gui/Xml/Svg

- **QtWidgets** (pervasive), **QtPrintSupport** (pdfeditormainwindow.cpp,
  pdfviewermainwindow.cpp, pdfprogramcontroller.cpp), **QtTextToSpeech** (pdftexttospeech.*,
  pdfsidebarwidget.cpp, pdfviewersettingsdialog.cpp — unguarded, hard requirement),
  **QtConcurrent** (10 files incl. pdfcompiler.cpp:586 QtConcurrent::run, PageMaster).
- NOT needed: OpenGL/OpenGLWidgets, Network, Multimedia, WebEngine, DBus, Sql.
- **PDFWidgetSnapshot is a red herring**: plain struct including only QRectF/QTransform —
  no QWidget dependency; our core compiles pdfwidgetsnapshot.cpp with Core/Gui/Xml/Svg only.
- Vendored CMakeLists: LibGui links PrintSupport+TextToSpeech+Xml+Svg; LibWidgets links
  Xml+Svg+Widgets; PageMaster links Concurrent; Viewer/Editor link Core/Gui/Widgets.

## 4. Excluded upstream internals check — none

- `git ls-tree 6bf5047 --name-only src/Pdf4QtLibCore/sources/` vs `ls` → ours is a superset
  (165 vs 157 files; the 8 additions are our RTL/search/recognize files).
- CMakeLists enumerations: `grep -oE 'sources/[a-z0-9_.]+\.(cpp|h)'` both sides, comm -23 →
  nothing dropped from the build (155 vs 147 entries).
- All 102 distinct `pdf*.h` includes across GUI resolve to core headers we ship or
  GUI-local headers.

## 5. Method pitfalls (reusable for any fork-compat audit)

1. **CRLF vs LF** makes cross-commit `git diff` useless in this repo — always
   `diff -w -B` on `git show <commit>:<path>` outputs (or `git diff -w`).
2. **comm path-prefix trap**: `git ls-tree --name-only` emits full paths
   (`src/Pdf4QtLibCore/sources/x.h`), `ls` emits bare names — `comm -23` then reports
   everything as missing. `sed 's|src/Pdf4QtLibCore/sources/||'` one side first.
3. **`-w` diff ≠ no removal**: clang-format one-liner→multi-line expansion still shows
   as -/+ pairs; verify each removed-looking signature still exists in HEAD before
   classifying a change as a signature change.
4. **Qt module classification**: strip `#include <Q` AND trailing `>`; umbrella headers
   like `<QtConcurrent>` leave `tConcurrent` (starts with lowercase 't') — handle the
   `Qt` prefix separately or you'll mis-bucket them into QtGui.
5. **Verify the claimed base**: the fork base SHA and the upstream tag SHA need not match —
   check content equality (`diff -w -B`) before treating "diff vs base" as "diff vs tag".
