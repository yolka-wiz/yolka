# WS2 audit verdict — GUI deps & Qt-version (2026-08-07, branch m12/gui-restore)

Independent parallel audit of the vendored GUI layers (Pdf4QtLibGui /
Pdf4QtLibWidgets / Pdf4QtEditor / Pdf4QtViewer / Pdf4QtPageMaster) BEFORE
they were wired. Verdicts are the "report-only" input the wiring workstream
(WS1, commit 84c1f848) and the build workstream consumed. No code was
changed by this audit; repo left clean.

## vcpkg verdict: needs NOTHING new

- `src/vcpkg.json` = `tbb, openssl, lcms, zlib, openjpeg, freetype,
  libjpeg-turbo, libpng, blend2d, harfbuzz, fribidi`.
- Upstream `vcpkg.json` at tag `v1.6.0.0` (via `git show v1.6.0.0:vcpkg.json`):
  exactly the first 9 — harfbuzz + fribidi are our RTL additions. Prior
  analysis confirmed.
- GUI CMakeLists contain ZERO `find_package` calls — dep surface is the
  core's. Non-Qt links in GUI layers:
  - `Pdf4QtLibWidgets/CMakeLists.txt:88` — `TBB::tbb` PUBLIC inside
    `if(LINUX_GCC)`; `LINUX_GCC` defined at core `src/CMakeLists.txt:54-56`,
    `find_package(TBB REQUIRED)` at :61 → already available.
  - `:95` — `blend2d::blend2d` PRIVATE → already a core dep.
  - `:91-93` — MINGW-only system libs (Secur32 Mscms Gdi32 User32 crypt32).
- GUI sources include NO third-party headers; `pdfplugin.h` is in the core
  (`Pdf4QtLibCore/sources/`); `QPluginLoader` usage is runtime-only.

## Qt-version verdict: compiles on Qt 6.8.2 (despite upstream README "Qt 6.9+")

Header-token sweep (method in `qt-cmake-vcpkg-build` skill →
`references/qt-version-api-audit-2026-08-07.md`): 400 unique `Q*::method`
tokens in GUI sources vs the installed Qt 6.8.2 headers → only 3 missing,
all `QTextToSpeech`/`QVoice` (unprovisioned MODULE, already compiled out by
commit 48d58fd8's `QT_TEXTTOSPEECH_LIB` guards — 5 verified guard sites:
pdfsidebarwidget.cpp:51,399; pdfviewersettingsdialog.cpp:38,88,875).
Qt 6.9-only QColorSpace members (`primaryPoints`, PerceptualQuantizer,
HybridLogGamma, CinemaGamut) — zero usage. `QColor::fromString` (Qt 6.8+)
used at 3 sites — OK. All used QImage/QPainter/QFont/QKeySequence APIs
present in 6.8.2. `setPlaceholderText` hits are QLineEdit (ancient);
PDFActionComboBox derives QLineEdit, not QComboBox.

## Linux pitfalls: none blocking

- **icon.rc** (all 3 apps list it unconditionally): empirically verified
  ignored on Linux — scratch project configure + build succeed (CMake emits
  no rule without an RC compiler). NOT a blocker; leave upstream CMake
  pristine.
- **.qrc files**: all 8 verified — every referenced file exists.
- **Platform branches**: all `#ifdef Q_OS_WIN/Q_OS_MAC` guarded;
  `pdfsendmail.cpp` keeps upstream's `#elif defined(Q_OS_UNIX) // TODO
  return false` (the `static_assert(false)` at :116 is dead code on Linux —
  see `#elif` grep trap below); `pdfwintaskbarprogress.cpp` has a no-op
  non-Windows impl; `WIN32_EXECUTABLE ON` / `MACOSX_BUNDLE ON` are no-ops
  on Linux.
- **Vendored sources pristine**: byte-identical to upstream v1.6.0.0 except
  the intentional TTS divergence (pdftexttospeech.cpp stub + guards in
  pdfsidebarwidget.cpp / pdfviewersettingsdialog.cpp + LibGui CMake link
  drop). Nothing else drifted.

## Wiring inputs (for the build workstream, NOT this audit)

- Qt modules the GUI needs beyond core's
  `find_package(Qt6 6.8 ... Core Gui Xml Svg Test)`: **Widgets,
  PrintSupport** (LibGui), **Concurrent** (PageMaster). All present on the
  box (qt6-base-dev 6.8.2); TextToSpeech deliberately absent. (Since
  applied by WS1.)
- `QT_INSTALL_DIRECTORY="${QT6_INSTALL_PREFIX}"` (LibGui CMake:90) resolves
  from the Qt6 find_package; `PDF4QT_*`/`INSTALL_INCLUDEDIR` vars come from
  the core CMake (INSTALL_INCLUDEDIR intentionally empty → export headers at
  build root, matches core).

## Traps that cost time (reusable)

- **`#elif` grep trap**: `grep -E "else"` does NOT match `#elif` — caused a
  false "static_assert Linux blocker" alarm. Read the full conditional chain
  before flagging (`grep -nE '#if|#elif|#else|#endif' <file>`).
- **Upstream path-prefix trap**: upstream keeps GUI dirs at repo ROOT, the
  fork vendors them under `src/` → `git diff <tag> -- src/...` shows every
  file as new. Compare content with
  `git show <tag>:<path> | tr -d '\r' | diff - <local>` (CRLF noise).
- **git-tag availability**: upstream tag `v1.6.0.0` is fetched locally —
  always diff against it before re-archaeologizing vendored code.
