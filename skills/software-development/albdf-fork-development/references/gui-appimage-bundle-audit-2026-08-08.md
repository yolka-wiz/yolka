# GUI AppImage bundle audit — "where are the editing features?" (2026-08-08)

Question answered: "we don't have editing features in the AppImage — how much
work to pull and bundle the pdf editor?" Verified by extracting the real
0.3.0 AppImage and reading the vendored GUI source.

## What the 0.3.0 AppImage actually contains

`APPIMAGE_EXTRACT_AND_RUN=1 ./albdf-0.3.0-x86_64.AppImage --appimage-extract`:
- `usr/bin/albdf-editor`, `albdf-viewer`, `albdf-pagemaster` (all 3 present)
- `usr/lib/libPdf4QtLibCore|Gui|Widgets.so.1.6.0.0` + Qt/system libs
- `usr/bin/qt.conf`; only the `xcb` platform plugin is bundled (offscreen
  fails inside the bundle by design — verify under xvfb with
  `QT_QPA_PLATFORM` unset)
- AppRun is a binary (standard AppImage runtime); default entry = whatever
  linuxdeploy `--executable` was given = **albdf-viewer**

Editor aliveness smoke:
`APPIMAGE_EXTRACT_AND_RUN=1 xvfb-run -a timeout 12 ./squashfs-root/usr/bin/albdf-editor <pdf>`
→ exit 124 = alive the whole 12s (good). `--help` under xvfb prints "PDF4QT Editor".

## Why editing seems missing (two separate causes)

1. **The AppImage launches the VIEWER, not the editor.**
   - Only `packaging/albdf-viewer.desktop` exists; build-appimage.sh runs
     `--executable .../albdf-viewer`.
   - Viewer initializes `Features(TextToSpeech|Tools)` (pdfviewermainwindow
     .cpp:233) → NO forms, NO undo/redo.
   - Editor initializes `PDFProgramController::AllFeatures`
     (pdfeditormainwindow.cpp:294) → annotation tools, forms, undo/redo,
     plugins.
   - Fix ≈ 15-30 min: add `albdf-editor.desktop`, change `--executable` to
     albdf-editor, rebuild.

2. **The deep page-content editor is a PLUGIN we never vendored.**
   - `PDFPageContentScene` (defined in pdfpagecontentelements.h:544) +
     `PDFPageContentEditorWidget` are NOT wired into the editor binary.
   - Upstream loads them from `Pdf4QtEditorPlugins/EditorPlugin` at runtime:
     `PDFProgramController::loadPlugins()` (pdfprogramcontroller.cpp:2495)
     uses QPluginLoader on `<appDir>/pdfplugins/*.so`
     (`PDF4QT_PLUGINS_DIR` = `${PDF4QT_INSTALL_LIB_DIR}/pdfplugins`).
   - Our src/CMakeLists.txt:114: "Pdf4QtEditorPlugins is intentionally NOT
     wired" (168 files / 9 plugins: EditorPlugin, Redact, Signature,
     ObjectInspector, Scanner, Dimensions, OutputPreview, SoftProofing,
     AudioBook).
   - ALL EditorPlugin deps are already vendored + building (scene, editor
     widget, processor, object editor) → vendoring is a CMake + packaging
     job, NOT a code port.

## Effort table (2026-08-08 verdict)

| Option | Work | Result |
|---|---|---|
| A. Launch editor by default | ~15-30 min | annotation tools + forms + undo/redo in AppImage |
| B. Vendor EditorPlugin | ~0.5-1 day (20 files, trivial CMake, bundle .so, gate) | canvas page-content editing |
| C. All 9 plugins | ~1-1.5 days | full PDF4QT parity |
| D. + update GUI from latest upstream | +31 GUI files | newer features, adds merge surface |

## Sequencing caveat

EditorPlugin depends on `pdfpagecontenteditorprocessor.{cpp,h}` — the exact
file upstream `ca6f467a` (Issue #238) modifies. Do the upstream core sync
FIRST, then vendor EditorPlugin, or the merge surface grows.

## Verification technique (reusable)

`readelf -d <bin>` → NEEDED libs; `--appimage-extract` → inspect contents;
`timeout 12 xvfb-run -a <bin> <pdf>` → 124 = alive; desktop files tell you
which binary the AppImage launches; Features flags in pdfviewermainwindow.cpp
vs pdfeditormainwindow.cpp tell you what each app enables.
