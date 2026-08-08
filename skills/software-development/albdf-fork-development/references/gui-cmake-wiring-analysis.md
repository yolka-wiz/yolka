# GUI CMake wiring analysis — 5 vendored dirs (verified 2026-08-07, analysis only)

Executes prong #1 of the gui-restore plan (see `gui-restore-vendoring-2026-08-07.md`).
All findings below were VERIFIED against the actual vendored files and the live host,
not guessed. Vendored CMakeLists are byte-identical to upstream tag `v1.6.0.0`
(only CRLF/LF line-ending diffs — check with `git diff --no-index --stat <(git show
v1.6.0.0:$d/CMakeLists.txt) src/$d/CMakeLists.txt`). Every listed source file exists;
every `.qrc` file reference resolves (checked with a python regex walk).

## Per-dir quick table

| Dir | Target | Type | Links (beyond root-provided Qt) | Qt modules | .qrc / .ui |
|---|---|---|---|---|---|
| Pdf4QtLibWidgets | Pdf4QtLibWidgets | SHARED lib | Pdf4QtLibCore(priv), TBB::tbb(pub, LINUX_GCC), blend2d(priv) | Core Gui Xml Svg **Widgets** | 7 .ui, no qrc |
| Pdf4QtLibGui | Pdf4QtLibGui | SHARED lib | Pdf4QtLibCore + Pdf4QtLibWidgets (priv) | Core Gui Widgets **PrintSupport TextToSpeech** Xml Svg | pdf4qtlibgui.qrc (116 svg icons), 13 .ui |
| Pdf4QtEditor | Pdf4QtEditor | exe | LibGui + LibWidgets + LibCore (priv) | Core Gui Widgets | app.qrc (app-icon.svg), icon.rc (ignored on Linux) |
| Pdf4QtViewer | Pdf4QtViewer | exe | same as Editor | Core Gui Widgets | app.qrc |
| Pdf4QtPageMaster | Pdf4QtPageMaster | exe | LibCore + LibWidgets (priv) — **NO LibGui** | Core Gui Widgets **Concurrent** | app.qrc + resources.qrc (64 svg), 7 .ui |

Dependency chain: `Core ← LibWidgets ← LibGui`; apps sit on all three except
PageMaster (LibGui-free). No target-name collisions with `albdf`/`Pdf4QtLibCore`.

## Wiring needed in src/CMakeLists.txt

- Extend the root `find_package(Qt6 ...)` with `Widgets PrintSupport Concurrent`.
- **Do NOT add TextToSpeech until the module exists on the box** (see blocker below).
- `add_subdirectory(Pdf4QtLibWidgets)` BEFORE `Pdf4QtLibGui` (LibGui links LibWidgets
  by name). Add the 3 apps after. Recommend gating behind a new option
  (`ALBDF_BUILD_GUI`) to keep the headless default; repo AGENTS.md currently forbids GUI.
- `set(CMAKE_INCLUDE_CURRENT_DIR ON)` is optional-but-safe (upstream gets it via
  `qt_standard_project_setup`); AUTOUIC already adds the uic output dir to target
  includes, so `.ui` files resolve without it.
- Do NOT wire: Pdf4QtEditorPlugins (runtime-loaded via core PDFPluginManager, degrades
  gracefully), `Pdf4QtLibGui/main.cpp` (exists but is NOT in upstream's source list —
  leave it out), translation machinery (qt_add_translations is root-level; skipping
  only costs untranslated UI strings).

## Gotchas (counter-intuitive, verified)

- **`INSTALL_INCLUDEDIR` is empty in BOTH upstream and our root.** GNUInstallDirs
  defines `CMAKE_INSTALL_INCLUDEDIR`, never the bare name. So
  `${CMAKE_BINARY_DIR}/${INSTALL_INCLUDEDIR}` = binary root everywhere, and the
  GENERATE_EXPORT_HEADER outputs (`pdf4qtlibwidgets_export.h`, `pdf4qtlibgui_export.h`)
  land at build root — consistent with our core's existing pattern. Do NOT "fix" this
  by defining INSTALL_INCLUDEDIR; it would diverge from upstream semantics.
- **`QT6_INSTALL_PREFIX` is not set by Qt6Config** → LibGui's
  `add_compile_definitions(QT_INSTALL_DIRECTORY="${QT6_INSTALL_PREFIX}")` expands to an
  empty def that no `.cpp/.h` uses — inert, same upstream. Leave it.
- **Qt module availability on this Debian box (Qt 6.8.2, qt6-base-dev):** Widgets,
  PrintSupport, Concurrent all ship in qt6-base-dev ✓. OpenGL/OpenGLWidgets, Network,
  Multimedia, SvgWidgets are NOT used anywhere in the GUI (grep-verified) — do not add.
- **`qt_standard_project_setup` / `qt_collect_translation_source_targets` /
  `qt_add_translations` are referenced only by the upstream ROOT CMake**, never by the
  5 vendored dirs — skipping them is safe.

## HARD BLOCKER: Qt6::TextToSpeech

`Pdf4QtLibGui` links `Qt6::TextToSpeech` and 3 files use it UNCONDITIONALLY (no
QT_CONFIG guards): `pdftexttospeech.cpp`, `pdfsidebarwidget.cpp`,
`pdfviewersettingsdialog.cpp` (`#include <QTextToSpeech>`, `QTextToSpeech::availableEngines()`).
On this box: no `Qt6TextToSpeech` cmake dir, nothing installed, and `qt6-texttospeech-dev`
is absent from the apt cache (only `libqt6texttospeech6` runtime shows up). Consequence:
adding LibGui with TextToSpeech in find_package fails at CONFIGURE for the whole tree.

Options: `apt install qt6-texttospeech-dev` (needs repo access), or fork-patch the 3
speech TUs out + drop the module (a tracked divergence from upstream).

## Build-risk order (first failure wins)

1. **Configure** (TextToSpeech missing) — blocks everything, even the core-only build
   if added naively to find_package.
2. **LibWidgets compile** — heaviest TUs (`pdfpagecontenteditorwidget.cpp`,
   `pdfcompiler.cpp`, `pdfdrawwidget.cpp`); core APIs they need are all present in our
   core, but our RTL changes touched `pdffont`/`pdftextlayout` → font/settings seams
   (`pdfviewersettings*`) are medium risk.
3. **LibGui link** (after TextToSpeech resolves) — 25 cpp / 13 ui; AUTOMOC/AUTOUIC/
   AUTORCC already ON at root; `pdfwintaskbarprogress.cpp`/`pdfsendmail.cpp` Windows
   branches are Q_OS_WIN-guarded (near-empty TUs on Linux).
4. **Apps + PageMaster** — trivial; `icon.rc` ignored on Linux (upstream-proven).

## Verification recipe (reusable for any vendored-dir audit)

```bash
# vendored == upstream? (line-ending-only diff = identical)
git diff --no-index --stat <(git show v1.6.0.0:$d/CMakeLists.txt) src/$d/CMakeLists.txt
# all sources listed in add_library/add_executable exist on disk
# all <file> refs in every .qrc resolve  → small python regex walk, see session
# Qt module presence: ls /usr/lib/x86_64-linux-gnu/cmake/ | grep -i <module>
```
