---
name: albdf-fork-development
description: "Use when developing in the albdf PDF4QT fork."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [albdf, pdf4qt, qt, cli, tdd, regression-testing]
    related_skills: [test-driven-development, systematic-debugging, qt-cmake-vcpkg-build, open-source-triage]
---

# albdf fork development (PDF4QT-based headless PDF CLI + library)

Use when working in any albdf checkout (e.g. `/home/agent/workspace/al-bdf-engine` main repo,
`wt-fix-render` worktree, fuzz harness repo `wt-infra-fuzz`). albdf is a fork of MIT-licensed
PDF4QT: a headless PDF library + `albdf` CLI (C++20, Qt 6, CMake + vcpkg manifest mode).

## 1. Read the binding contracts FIRST (they override habits)

- Repo root `AGENTS.md` in full, then `src/AGENT.md`, `src/PdfTool/AGENT.md` (exit-code
  contract), `src/UnitTests/AGENT.md` (runTool pattern, compile defs), `src/Pdf4QtLibCore/AGENT.md`,
  and the `docs/PROBLEMS.md` entry for your task. Task plans live in `plans/` — read the
  execution plan for your milestone before touching code.
- Ground rules: determinism above all (no timestamps/random IDs in output), headless
  (`QT_QPA_PLATFORM=offscreen`), CLI-first, TDD (RED test committed first), small
  Conventional Commits, no scope creep, never fake results.
- Exit-code contract: `0` success, `7` ErrorInvalidArguments, `4` ErrorDocumentReading.
  Tests must assert the exact documented code, NOT just `!= 0`.

## 2. Build & test (exact commands for this host)

- **vcpkg is at `/home/agent/vcpkg-cache/vcpkg` — NOT `/workspace/vcpkg` as `src/AGENT.md`
  claims.** Verify with `ls` before configuring; the AGENT.md path is stale on this host.
- New sources must be added to the relevant `CMakeLists.txt` (files are NOT globbed) or they
  silently never build.
- Use a Release build for reproducer timing; Debug/ASAN builds live in `build-asan/`.

```bash
export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake -DALBDF_BUILD_TESTS=ON
cmake --build build -j$(nproc)
QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure
```

## 3. Format gate (`ci/run-ci.sh`) — vendored upstream files are exempt

- The gate checks `git diff --name-only 6bf5047..HEAD -- '*.cpp' '*.h'`, minus a grep
  exclusion list, with `clang-format --dry-run --Werror` on WHOLE files.
- **Pristine vendored upstream files (e.g. `src/PdfTool/pdftoolrender.cpp`,
  `src/Pdf4QtLibCore/sources/pdfutils.cpp`) fail the repo's `.clang-format` even untouched**
  (upstream formatting differs). If you modify one, add it to the exclusion list in
  `ci/run-ci.sh` (the `grep -vE` lines) — do NOT `clang-format -i` the whole file (destroys
  cherry-pick diffs; the gate's own comment says modified upstream files are excluded and
  added lines are styled to match the surrounding code).
- New authored files MUST pass `clang-format --dry-run --Werror`.
- **Vendored WHOLE dirs (the 5 GUI dirs, M12) need DIRECTORY-level
  exclusions** — when `git archive <tag> <dir> | tar -x` adds 358
  upstream-formatted files, the gate flags every one. Add
  `| grep -vE '^src/Pdf4QtLibGui/'` (trailing slash) per dir to the
  `grep -vE` chain, NOT per-file lines. CI's format job is the fast canary
  (fails while build/asan pass). Full detail + the patch-tool backslash
  double-escape trap (`\\.` → `\\\\.` breaks the regex silently — verify
  with `cat -A`, fix doubles with Python byte replace) and the
  branch-mixup trap (a fix committed while a child's branch is checked out
  lands on the WRONG branch — check `git branch --show-current`, then
  `git cherry-pick` onto the PR branch) are in the `qt-cmake-vcpkg-build`
  skill §13 (hit twice, 2026-08-06/07).
- The pre-commit hook regenerates `REPO_MAP.md`; let it ride along in the commit.

## 4. CLI integration tests (Qt Test, QProcess)

- Canonical pattern: `src/UnitTests/tst_*.cpp` with the `runTool()` QProcess helper
  (copy from `tst_pageopstest.cpp`). Register in `src/UnitTests/CMakeLists.txt`:
  `add_executable` + `add_test` + `add_dependencies(UnitTestsX albdf)` +
  `set_tests_properties(... ENVIRONMENT "QT_QPA_PLATFORM=offscreen")` + a compile def for
  the fixture path (e.g. `TEST_MULTIPAGE_PDF=.../tests/fixtures/multipage.pdf`).
- End file with `QTEST_GUILESS_MAIN(Class)` + `#include "tst_x.moc"`.
- **Crash-vs-error assertions:** record BOTH `process.exitStatus()` and `process.exitCode()`;
  assert `exitStatus == QProcess::NormalExit` AND `exitCode == <documented code>`. A SIGABRT
  child reports `CrashExit` — asserting only the exit code can miss signal deaths.
- **Hang regression tests:** bounded `waitForFinished(timeoutMs)` then `kill()`; assert a
  `finishedInTime` flag. Keep the suite from hanging the whole ctest run.
- **Reproducing OOM/allocation bugs:** check `free -g` and `swapon --show` first; cap the
  child with `ulimit -v <bytes>` so it fails fast (bad_alloc / empty output) instead of
  OOM-killing the test host or thrashing for the full timeout.
- Determinism: hash outputs with `QCryptographicHash::Sha256` and compare across two runs.

## 5. Pitfalls (fuzz-crash class, learned the hard way)

- **SIGABRT 134 + "Qt Concurrent has caught an exception thrown from a worker thread"**:
  an exception (usually `std::out_of_range` from `vector::at`/`QList::at` — e.g.
  `PDFCatalog::getPage` uses `m_pages.at(index)`) escaped a Qt Concurrent worker. Qt
  Concurrent cannot propagate exceptions; the process aborts. Fix = validate inputs
  (page ranges, options) BEFORE dispatching to the worker pool, and return the documented
  error code — never try to catch inside the worker.
- **Bounding the parameter ≠ bounding the resource:** clamping `--image-res-dpi` to 72..6000
  still permits a 51000x66000 px image (612x792 pt Letter at 6000 dpi ≈ 13.5 GB RGBA) →
  hang/OOM. Validate the COMPUTED downstream quantity (image dimensions) against the
  library's own envelope (`PDFPageImageExportSettings::getMaxPixelResolution()` = 16384)
  before any allocation.
- **Doc comment vs implementation:** `PDFClosedIntervalSet::parse(first, last, ...)` claims
  in its header doc that parsed numbers must be within `[first, last]` but historically only
  used them as defaults for open-ended ranges ("N-", "-N"), accepting out-of-range intervals
  silently. When a doc comment states a contract, verify the implementation enforces it —
  fix at the parse site so every caller (render, delete-page, fetch-*, ...) is protected.
- Check the DB (`python3 scripts/db.py`) for task context, but never close DB tasks —
  the orchestrator closes them (task-done requires `--ref <sha>` evidence).
- **`albdf render <doc> <out>` with an output path that doesn't resolve as expected
  (e.g. missing `.png` extension) still exits 0 but drops `Image_N.png` next to the
  INPUT document** (observed: `src/tests/fixtures/Image_1.png`). After any render smoke
  check, `git status` and delete stray `Image_*.png` — it won't be in your commit.
- **Fixing a DOCUMENTED degradation: existing tests may PIN the buggy behavior.**
  When the fix lands, the pin flips from pass to fail — that's the fix working, not a
  regression. Real case (R#4, 2026-08-07): `tst_rtladdtexttest.cpp::test_rtlKeepsLtrIntact`
  asserted the DEGRADED extraction `ملس` and its comment documented "second add-text
  ... does not preserve /ActualText ... So this mixed case still degrades" as current
  behavior; after the R#4 fix the output is correct (`ملاس`) and the assertion fails.
  When fixing a known limitation, grep the test suite for assertions of the degraded
  output (and for PROBLEMS.md entries being quoted as expected behavior) BEFORE
  committing the fix, and update the pin as part of the fix commit.
- **Shared-worktree baseline isolation:** parallel agents' UNCOMMITTED changes coexist
  on the shared `main` worktree (R#4 session: uncommitted pdfrtltextnormalizer/GUI/
  tst_searchtexttest edits by another agent). Before attributing a full-suite failure
  to YOUR change, prove the baseline with `git stash push -m <name> -- <your exact
  file list>` → rebuild → rerun the failing test → `git stash pop`. NEVER bare
  `git stash` (grabs everyone's changes) and never `git add -A` (stage only your
  paths). Also: verify dispatch-brief claims against the LIVE branch — the R#4 brief
  suspected ci/run-ci.sh was missing format-gate exclusions for the two touched files,
  but they were already present (grep first, patch second).
- **Content-editor /ActualText preservation (R#4) — the reusable fix pattern** is in
  `references/content-editor-actualtext-r4-2026-08-07.md`: capture via
  `performMarkedContentBegin/End` overrides + `Item::actualText` (UTF-16BE+BOM,
  manual byte encode — `QString::toUtf16()` is native-endian, WRONG for PDF),
  per-run re-emission through `<actualText v="HEX"/>` XML markers (NOT a whole-element
  BDC wrap: the layout generator replaces the full BDC..EMC glyph range, so a mixed
  LTR+RTL element would lose its unmarked runs), nesting stack with outermost-span-only
  recording, and the stale-test pin above.
- **Visual-order lam-alef collapse (S#3) — search engine must normalize the FLOW in
  visual order, the QUERY in logical order.** Root cause of a real bug (`4cabbf7a`,
  2026-08-07) that made document-level `PDFTextSearchEngine::search` return 0 matches
  for ANY word containing lam-alef (e.g. `سلام`) written by `add-text --rtl`: the
  query collapses `لا`→`ل` in LOGICAL order (`سلام`→`سلم`, 3 chars), but extracted
  PDF flow text is VISUAL order, where the ligature appears as the REVERSED pair `ال`
  (ا then ل) — so the flow kept 4 chars and the 3-char query never matched. Fix:
  `PDFRTLTextNormalizer::Options::visualOrder` (default false) additionally collapses
  `ال`→`ل`, and the engine enables it ONLY on the flow-side normalization (step 3),
  never the query side (step 1 — a logical-order `ال` is the definite article and MUST
  NOT collapse). The GUI search adapter exposed this because the legacy CLI tests only
  searched via `searchFlow` with hand-built flows or non-lam-alef words — document-level
  coverage was missing. **Measurement trap that hid it:** `grep -c "سلام"` on
  `search-text` output counts the QUERY ECHO line, falsely "confirming" a match — always
  read the `Matches` table rows (or assert count) instead. Regression:
  `test_engineSearchSalam` in `UnitTestsSearchText`. Full debug path (byte-identical
  fixture vs fresh file, Hebrew-vs-Arabic divergence, char-rect probe):
  `references/rtl-search-visual-order-lamalef.md`.

## 6. Running the full local CI gate (`ci/run-ci.sh`) — verification runs

Use when asked to run the CI gate locally (e.g. GitHub Actions runners down) or to verify a
branch pre-merge. The gate is READ-ONLY w.r.t. the repo: it only writes build dirs
(`src/build`, `src/build-asan`) and `/tmp/ci-*.log`; git status stays clean. Do NOT commit,
push, or close DB tasks during a verification run.

- **The script's own default `VCPKG_ROOT=/workspace/vcpkg` is wrong on this host** — always
  `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg` first (same stale path as AGENT.md).
- 4 stages: (1) Release configure+build, (2) offscreen ctest, (3) ASAN/UBSAN Debug build +
  ctest (creates `build-asan/` fresh — 15-40 min), (4) clang-format gate on authored files.
- **MUST run in background with notify_on_complete** — total run exceeds the foreground
  timeout. Capture the exit code explicitly:
  `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg; cd <repo> && bash ci/run-ci.sh > /tmp/ci-run.log 2>&1; echo "CI_EXIT_CODE=$?"`
- Per-stage logs (script writes these): `/tmp/ci-build.log` (1), `/tmp/ci-ctest.log` (2),
  `/tmp/ci-asan-cfg.log` + `/tmp/ci-asan-build.log` + `/tmp/ci-asan-ctest.log` (3). Stages 1-2
  are seconds-fast when `build/` is already up to date ("ninja: no work to do").
- Verify: `cat /tmp/ci-run.log` → 4 stage headers, `clang-format gate OK (N files)`, final
  `CI: ALL GREEN`; tail ctest logs for `100% tests passed, 0 tests failed out of N`;
  `grep -c FAILED /tmp/ci-run.log` == 0; then `git status --short` clean.
- `process wait` clamps to ~180s per call — rely on the completion notification and re-wait.
- Stage-selection flags exist: `--skip-release`, `--skip-asan`, `--skip-format`,
  `--only-format`. Full runbook in `references/ci-gate-runbook.md`.
- **GUI stage: `bash ci/run-ci.sh --gui` (or `ALBDF_CI_STAGE=gui`)** — runs the
  optional vendored-GUI build + headless smoke INSTEAD of the 4 headless stages,
  then exits (headless gate untouched; added 2026-08-07, commit `7dc95d50`).
  Configures `src/build-gui` with `ALBDF_BUILD_GUI=ON`, builds
  `-j"$(nproc)"`, then `QT_QPA_PLATFORM=offscreen bash src/tests/gui-smoke.sh`
  (logs `/tmp/ci-gui-build.log`, `/tmp/ci-gui-smoke.log`). Green run prints
  `OK: viewer = .../build-gui/bin/Pdf4QtViewer`, `OK: --help exits 0 (offscreen)`,
  `OK: [offscreen] viewer stayed alive 8s ...`, then `CI: ALL GREEN`, exit 0.
  Hosted-CI `gui` job is non-gating (continue-on-error) and installs xvfb; no
  toolchain change needed (Widgets/PrintSupport/Concurrent are in aqt qtbase).
  Gotcha: the stage's configure omits `-DALBDF_BUILD_TESTS` — reconfiguring a
  pre-existing build-gui dir flips tests OFF (ninja drops test targets, no
  recompile; stale test binaries linger in `bin/`, harmless). Exact transcript:
  `references/gui-ci-stage-2026-08-07.md`.
- **Perf benchmark job gotcha (fixed 2026-08-07, commit `d009c4b`): a failing
  benchmark job is usually a PARSE bug, not a perf regression.** The 1000-page
  doc's `albdf info` prints `Page count  1,000` (locale thousands separator) but
  `scripts/benchmark.sh` compared the awk `$3` against the bare string `"1000"`
  → EVERY op asserted FAIL (`op=info,ms=29,ok=0`) even at 29 ms. Same trap for
  the search-matches count. Fix: strip commas in awk before comparing
  (`awk '/Page count/ {gsub(/,/, "", $3); print $3; exit}'`). Second gotcha:
  without `QT_QPA_PLATFORM=offscreen` the binary aborts (exit 134) with no
  display — the script must export offscreen itself inside `time_op` rather
  than relying on CI's job-level env. When a benchmark job goes red, first
  check the script's assertions for locale/format assumptions before hunting
  for a real regression.

## 7. Vendored GUI layer wiring (Pdf4QtLibGui/Widgets/Editor/Viewer/PageMaster)

**IMPLEMENTED & CONFIGURE-VERIFIED (M12 WS1, commit 84c1f848).** The wiring
(analysis first, see `references/gui-cmake-wiring-analysis.md`): the 5 vendored dirs
wire up with NO new variable definitions; root `find_package(Qt6 ...)` extended with
`Widgets PrintSupport Concurrent`; `set(CMAKE_INCLUDE_CURRENT_DIR ON)`;
`option(ALBDF_BUILD_GUI ... OFF)`; `add_subdirectory` order inside `if(ALBDF_BUILD_GUI)`:
`Pdf4QtLibWidgets` BEFORE `Pdf4QtLibGui`, then the 3 apps. Configure with
`-DALBDF_BUILD_GUI=ON` succeeds (seconds, warm vcpkg cache) and all 5 targets appear;
a GUI-OFF configure yields 0 GUI targets (headless default preserved). Exact commands +
verification: `references/gui-cmake-wiring-implemented-2026-08-07.md`. Key gotchas:
`INSTALL_INCLUDEDIR` and `QT6_INSTALL_PREFIX` are empty in upstream
too (export headers land at binary root; the QT_INSTALL_DIRECTORY def is inert) — do not
"fix" them; PageMaster does NOT link LibGui; `Pdf4QtLibGui/main.cpp` is intentionally not
in the source list. **TextToSpeech blocker RESOLVED (2026-08-07, compile-out
patch commit `48d58fd8`, configure re-verified with `ALBDF_BUILD_GUI=ON`):** do NOT
re-add the module to find_package; the stub/guards are a tracked fork divergence.
Qt modules NOT needed (do not add): OpenGL, Network, Multimedia, SvgWidgets, TextToSpeech.
GUI stays OPTIONAL (default OFF): ADR-0002 addendum (M12) records that the headless
contract still binds — core+CLI+tests must never depend on GUI code. **Compile-out recipe for an
unprovisioned Qt module (user-directed 2026-08-07):** (1) rewrite the
module's main TU (`pdftexttospeech.cpp`) as a NO-OP stub that preserves the
exact class API — same constructor/methods/signals, `m_textToSpeech=nullptr`,
`isValid()` returns false so the UI feature auto-hides (sidebar Speech page
disappears via the existing `!m_textToSpeech->isValid()` gate), and
`initializeUI()` populates controls in a disabled "Unavailable" state; keep
the forward-declared `QTextToSpeech*` member (a pointer to a forward-declared
class compiles fine without the module); (2) guard the OTHER files' direct
usage with `#if defined(QT_TEXTTOSPEECH_LIB)` around both the `#include
<QTextToSpeech>` AND the call sites (e.g. `QTextToSpeech::availableEngines()`
→ empty QStringList, `setSpeechEngine()` body → `Q_UNUSED` stub) — the macro
is defined only when the module is linked, so the code path is dead by
default but restores automatically if the module is provisioned later;
(3) drop the module from the target's `target_link_libraries`; (4) mark the
divergence with an `// albdf:` comment + restore-from-upstream note in the
stub so it survives cherry-picks. Verify guards are balanced
(`grep -c '#if defined(QT_TEXTTOSPEECH_LIB)'` per file) and no UNGUARDED
`#include <QTextToSpeech>` remains. This is a fork divergence — document it
in PROBLEMS.md. **API-compat prong (same day, verified):** the
vendored GUI COMPILES against our modified core — all changed/added core headers are
additive or signature-identical (details + per-API verdict table in
`references/gui-api-compat-audit-2026-08-07.md`). Four behavioral deltas to know:
`PDFClosedIntervalSet::parse` now rejects out-of-range (select-pages dialog pops an error),
`PDFTextLayoutGenerator` applies /ActualText repair (only affects ActualText-bearing docs),
`PDFDocumentBuilder` writes fixed-epoch CreationDate/ModDate, and the page-content-editor
XML round-trip sanitizes C0 chars + FixedNotation numbers. Reusable method: compare commits
with `diff -w -B` on `git show <sha>:<path>` (CRLF noise makes plain git diff useless here).
**Dependency & Qt-version audit verdict (WS2, parallel):** GUI needs NO new vcpkg deps
(upstream vcpkg.json == our 9 core deps + harfbuzz/fribidi) and the vendored sources
compile on Qt 6.8.2 — 400-token header sweep found only TTS APIs missing, all behind the
compile-out guards; icon.rc is silently ignored on Linux and all .qrc references exist.
Vendored tree is pristine except the TTS divergence. Full verdict + traps in
`references/gui-deps-qt-audit-ws2-2026-08-07.md`.

**GUI BUILD VERIFIED (WS5, commit `7b497852`, 2026-08-07):** the full
`cmake --build src/build-gui -j$(nproc)` with `ALBDF_BUILD_GUI=ON` compiled
**clean on the first attempt — zero fixes needed** (270/270 targets, exit 0).
All 5 targets built: `Pdf4QtLibWidgets` → `src/build-gui/lib/libPdf4QtLibWidgets.so.1.6.0.0`,
`Pdf4QtLibGui` → `libPdf4QtLibGui.so.1.6.0.0`, and the 3 apps →
`src/build-gui/bin/Pdf4QtViewer|Pdf4QtEditor|Pdf4QtPageMaster` (Viewer/Editor
are ~29 KB thin mains linking the shared libs; PageMaster ~1.3 MB). The WS1
API-compat audit was correct: the vendored GUI compiles against our modified
core with NO API mismatches, and the 48d58fd8 TTS compile-out holds (no
unguarded `QTextToSpeech` left). `bash src/tests/gui-smoke.sh` passes exit 0
under offscreen (no xvfb fallback needed on this host): `--help` OK, viewer
alive 8s with gui-rtl.pdf open, clean SIGTERM. Core suite stays green:
`QT_QPA_PLATFORM=offscreen ctest --test-dir src/build` = 14/14. RTL round-trip
note: the GUI apps have NO headless text-export flag in the v1.6.0.0 CLI
surface (checked `--help` of all 3 + grep) — GUI-level text extraction is not
possible headlessly; the fixture round-trips via the core CLI instead
(`albdf fetch-text gui-rtl.pdf` → `مالس`, documented visual order). Build
dirs: GUI builds into `src/build-gui` (separate from `src/build`), nothing
core/CLI/test related is touched by the GUI build.

**Headless GUI smoke scaffold READY (WS4, commit `1a7f2af2`, viewer since built — WS5):**
`src/tests/fixtures/gui-rtl.pdf` (deterministic RTL `سلام`, sha256
`db787c30…`, regenerable via `add-text --rtl --font NotoNaskhArabic --lang ar`
— byte-stable with or without `SOURCE_DATE_EPOCH`) + `src/tests/gui-smoke.sh`
(exit 0/1/2; fails loud "Viewer not built — run with ALBDF_BUILD_GUI=ON" until
the GUI builds; aliveness-under-timeout open check, fixture hash guard,
offscreen→xvfb fallback that must `env -u QT_QPA_PLATFORM`). Full recipe,
stub-verification method, and PDF4QT-specific gotchas (QApplication is
constructed before the parser, so `--help` needs the platform fallback too):
`references/gui-headless-smoke-2026-08-07.md`.

**GUI text-input RTL audit DONE (2026-08-07, audit-only, main @ 9f5e1338):** no GUI
path uses `PDFRTLTextEngine` — every commit-visible text path is raw
QLineEdit/QTextEdit/QPainter::drawText/QTextLayout. Full file:line map of all 11
text-input paths (canvas textbox tool, form fields, FreeText, sticky notes, content-editor
text items, find, sidebar, settings, XMP metadata) with commit-to-doc status, RTL-today
assessment, and minimal fix per path: `references/gui-text-input-rtl-audit.md`. Key facts
for future GUI-RTL work: (1) the one choke point that fixes form fields AND FreeText at
once is `PDFDocumentBuilder::updateAnnotationAppearanceStreams`
(pdfdocumentbuilder.cpp:1489-1575) → `annotation->draw()` → PDFContentStreamBuilder —
branch there to emit a `PDFRTLTextEngine` Type0 font + shaped fragment for RTL text,
keeping `/V`/`/Contents` logical; (2) the canvas textbox tool
(`PDFCreatePCElementTextTool`, pdfpagecontenteditortools.cpp:669-798) commits ONLY to the
in-memory `PDFPageContentScene` — no scene→content-stream serializer exists in the
vendored GUI, so it is screen-only (prior analysis confirmed); (3) the content-editor
text-item dialog (`pdfpagecontenteditorediteditemsettings.cpp:253-256`) sets
`m_itemsAsText` but never regenerates the glyph `m_textPath` — editing text there does
NOT change the document (stale-glyph trap); (4) form-field commit is
`setFocusImpl` → `PDFObjectFactory::createTextString(m_textEdit.getText())` →
`setFormFieldValue` (pdfwidgetformmanager.cpp:1634-1657 / :1576-1599).
**CORRECTION (2026-08-07, source-verified):** the find dialog is NOT RTL-correct —
both `PDFAdvancedFindWidget::performSearch` (pdfadvancedfindwidget.cpp:292,312) and
`PDFFindTextTool::performSearch` (pdfwidgettool.cpp:610,622) call the legacy
`PDFTextLayoutStorage::find` → `PDFTextFlow::find` = plain `m_text.indexOf`
(pdftextlayout.cpp:1353); `PDFTextSearchEngine` is referenced nowhere in any GUI file.

**WS-A (2026-08-07, adapter committed `088c1b09` after orchestrator consolidation; ALL GREEN):** both find entry points now route PLAIN-TEXT
queries through `PDFTextSearchEngine` via a new adapter
`src/Pdf4QtLibWidgets/sources/pdfwidgetrtlsearch.{h,cpp}`
(`pdf::searchDocumentPlainTextRTL(document, textLayoutStorage, query, caseSensitivity,
pageFirst, pageLast)` → `PDFFindResults`); regex/whole-word/wildcard intentionally stay
on the legacy path. The GUI link failure during the agent run was the stale-core-.so trap
(below) — the orchestrator rebuilt the core target and the full GUI linked clean.
Final state: 16/16 ctest green, `gui-smoke.sh` passes, and `search-text "سلام"` on the
RTL fixture now returns 1 match (was 0 — see S#3). Full record: exact diffs,
mapping contract, compile fixes, unit test recipe:
`references/gui-search-engine-adapter-2026-08-07.md`.

**Match→PDFFindResult mapping contract (source-verified + compiles, WS-A):**
- `PDFTextSelectionItem` = `std::pair<PDFCharacterPointer, PDFCharacterPointer>` (block/
  line/char indices) — NOT rects. `PDFTextSelectionPainter::draw` (pdftextlayout.cpp:
  1637-1651) resolves pointers via `block.getCharacterRangeBoundingPath` against the
  WIDGET's own text layout (`PDFTextLayoutGetter` from the compiler storage). Selection
  items MUST reference that layout, never the engine's flow items.
- `PDFTextLayoutStorage::getTextLayout(pageIndex)` returns a **copy by value**
  (deserialized from the storage blob). `createTextSelection` is NOT thread-safe and
  MUTATES the layout (angle transforms) → always call it on the copy, never on a
  shared/storage layout (data race with the async compile thread).
- `createTextSelection(pageIndex, rect.topLeft(), rect.bottomRight())` is geometric
  (nearest char right of p1 / left of p2) and works directly from `Match.boundingRect` —
  the audit-approved mapping is usable, no span-based fallback needed. Extract items by
  iterating `selection.begin()/end()` and copying `it->start`/`it->end` —
  `PDFTextSelection` has NO public getItems().
- `PDFFindResult::operator<` reads `textSelectionItems.front()` → results with EMPTY
  selection items break the widget's `std::sort` (Q_ASSERT debug / UB release). Drop
  unrenderable matches in the adapter (also correct: they'd paint nothing anyway).
- `PDFTextSearchEngine::searchFlow` is a NON-const member — the engine instance cannot
  be `const`. Build the flow yourself via
  `PDFDocumentTextFlowFactory::create(document, pageIndices, Algorithm::Layout)`
  (exactly what `search()` does internally; Layout = PDFTextLayoutGenerator +
  `PDFTextFlow::createTextFlows(SeparateBlocks|RemoveSoftHyphen)`, the same machinery
  as the GUI compiler) and reuse it for `context` (covered items' text, visual order).
- `Match.matchedText` is VISUAL order for RTL (e.g. fixture `سلام` matches as `مالس`-ish
  presentation forms) — a test asserting `matchedText.contains(u"سلام")` in LOGICAL
  order FAILS; assert match count == 1 + non-empty matchedText + a near-miss negative
  control (e.g. `شلام` → 0) instead.
- Namespace: `pdfwidgettool.cpp` is inside `namespace pdf` (unqualified call);
  `pdfadvancedfindwidget.cpp` is in `namespace pdfviewer` (needs `pdf::` prefix).
- `PDFDocumentReader` lives in `pdfdocumentreader.h` (NOT pdfdocument.h) — forgetting it
  is a hard compile error (`PDFDocumentReader is not a member of pdf`).

- **GUI link fails with `undefined reference to <symbol>` while the symbol EXISTS in
  core source (seen: `PDFPageContentEditorProcessor::performMarkedContentBegin/End`,
  defined in pdfpagecontenteditorprocessor.cpp:155/212 since `e9eedb18`):** the
  pre-existing `libPdf4QtLibCore.so` in `build-gui/lib/` is STALE — Ninja sees the core
  target as up-to-date and never relinks it, so the .so lacks symbols added by recent
  commits. Fix: force `cmake --build src/build-gui --target Pdf4QtLibCore` (or clean
  rebuild) BEFORE debugging your own code. Same class as the documented "stale pre-merge
  albdf binary" trap — rebuild from clean before trusting a baseline.

**GUI↔core text wiring audit VERIFIED (2026-08-07, report-only):** library-only path
confirmed — `Pdf4QtLibGui/CMakeLists.txt:99` links LibCore+LibWidgets, NO PdfTool;
CLI text commands are consumers of the same core classes (never shell out). CLI RTL
add-text **bypasses `PDFPageContentEditorProcessor`** (pdftooladdtext.cpp:200-537:
fresh stream + font-key merge) — new GUI RTL text should mirror that to sidestep R#4;
R#4 fix design: base processor ALREADY has `performMarkedContentBegin/End` virtuals
(pdfpagecontentprocessor.h:674-682) that the editor processor never overrides (only
10 overrides, h:251-260); builder has zero BDC/EMC/ActualText (writeEditedElement,
pdfpagecontenteditorcontentstreambuilder.cpp:538-646); fix = capture /ActualText on
`PDFEditedPageContentElementText::Item` (h:150-157) + re-emit in writeText; do NOT
add a 4th element type (ripples into `PDFPageContentElementEdited` drawing).
`PDFFindResult` is core-defined (pdftextlayout.h:304-318); Match→PDFFindResult map
via `PDFTextLayout::createTextSelection(boundingRect)` (h:449-453). **STALE:**
`rtl-through-gui-integration.md` says the GUI is "NOT wired into the build" and cites
pdfpagecontentelements.cpp:2654 as the textbox commit hook — superseded (build green
7b497852; real hook is finishEditing, pdfpagecontenteditortools.cpp:787-798). Full
file:line map + gap list: `references/gui-text-wiring-audit-2026-08-07.md`.

## 8. Form-field appearance streams (M14, WS-A) — verified headless reality

**Headless form-fill emits NO appearance stream at all — not tofu.** Verified
2026-08-08 at `e667fe0a` (16/16 ctest green): `albdf form-fill form.pdf out.pdf
--field name --value 'سلام'` exits 0 and writes `/V (\xD8\xB3\xD9\x84\xD8\xA7\xD9\x85)`
(raw UTF-8, logical) but the output contains **no `/AP`, no `/FontFile2`, no
`/Type0`, no `/Subtype /Form`**. Root cause (source-verified): the form-field AP
chain is `PDFFormFieldText::setValue` (pdfform.cpp:983) →
`builder->updateAnnotationAppearanceStreams(widget)` (pdfdocumentbuilder.cpp:1489)
→ `annotation->draw(parameters)` (:1533) → `PDFWidgetAnnotation::draw`
(pdfannotation.cpp:3249) → `formManager->drawFormField(...)` — which is a
`Q_UNUSED` **no-op** in core (pdfform.cpp:914-919). Real AP drawing exists only in
the optional GUI `PDFWidgetFormManager` (Pdf4QtLibWidgets). This CORRECTS the
earlier audit claim ("one choke point fixes form fields AND FreeText") in
`references/gui-text-input-rtl-audit.md`: for form fields the painter path is dead
in headless, so an RTL branch must generate the AP **directly** (bypass
`annotation->draw`), not just replace the font inside it.

**Code-path map (all source-verified, exact lines):**
- `PDFToolFormFill::execute` (pdftoolformfill.cpp) → `field->setValue(parameters)`
  with `parameters.modifier = &modifier`, `parameters.formManager = &formManager`
  (a bare core `PDFFormManager` — `setDocument` parses `m_form` only when the
  `PDFModifiedDocument` has `Reset` flag; the default ctor sets `Reset`).
- `PDFFormFieldText::setValue` → `builder->setFormFieldValue(fieldRef, value)`
  (`mergeTo(fieldRef, {V: value})`, pdfdocumentbuilder.cpp:5935) THEN
  `builder->updateAnnotationAppearanceStreams(widget)` per widget — so the fresh
  `/V` is already in the builder's storage when AP generation runs.
- `getDrawKeys`: base `PDFAnnotation::getDrawKeys` returns exactly
  `{Normal, ""}` (pdfannotation.cpp:310-315); text fields fall through to it.
- The generic AP loop builds a Form XObject via
  `copyFrom({contentStream.resources, contentStream.contents})` +
  `mergeTo(formRef, formFactory)` + `appearanceStreams[key] = formRef`, then
  merges `/AP << /N ... >>` (+ `/Rect`) into the annotation (lines 1544-1648).
  An RTL branch can mirror this shape.

**Proven RTL-embedding building blocks** (from the CLI add-text driver,
pdftooladdtext.cpp:181-423, all compile-verified): `PDFRTLTextEngine::create(
settings, fontKey)` returns `{fontDictionary (Type0+FontFile2 keyed by fontKey),
contentFragment (BT..ET, visual order, /ActualText), hasRTL, errors}`;
`builder->replaceObjectsByReferences(fontDictionary)` embeds nested streams as
objects; compress the fragment with `PDFFlateDecodeFilter::compress` →
`PDFObject::createStream` → `builder->addObject`; merge into page/AP Resources.
Pick a free `F<N>` key by resolving the target `/Resources` (which may be an
INDIRECT reference) — the RTL font must not collide with existing keys.

**Open decision (not yet resolved — session ended before GREEN):** core
`fonts.qrc` bundles ONLY Liberation fonts (Latin) — there is no Arabic font in
core resources. The RTL AP path needs a font source; candidate options are (a)
vendor an OFL Arabic font into `fonts.qrc`, (b) add a `--font` option to the
`form-fill` CLI (mirrors add-text), or (c) plumb fontData through the
`PDFFormManager`/builder. Also undecided: whether the builder's `m_formManager`
is set in the CLI path (pdftoolformfill.cpp does NOT call
`modifier.getBuilder()->setFormManager(...)` — verify before relying on
`getFormFieldForWidget` inside `updateAnnotationAppearanceStreams`; reading `/V`
straight from the builder storage avoids the dependency).

**RED-test recipe (designed, fixture-verified):** extend the EXISTING
`tst_formsignaturetest.cpp` suite with a private slot (no new CMake target —
`UnitTestsFormSignature` is registered at src/UnitTests/CMakeLists.txt:242, but
you must ADD `TEST_FONT_ARABIC` compile def to that target). The form fixture is
EMBEDDED inline in the test cpp (object 8 = merged field+widget, `/T (name)`),
NOT a file on disk — replicate it via a Python probe script when testing the CLI
by hand. `form-list` default text codec is utf8 (`getDefaultEncoding` → "utf8"),
so an Arabic round-trip assertion (`stdOut.contains(QString::fromUtf8("سلام"))`)
works. Assert on raw output bytes: `/AP` + `/FontFile2` present after filling
`name` with an Arabic value → fails at baseline (no AP at all).

**Split contract (M14):** WS-A owns the form-field path; WS-B owns the FreeText
annotation AP path — BUT (verified 2026-08-08) WS-B's RTL branch lives in
`PDFDocumentBuilder::updateAnnotationAppearanceStreams` (pdfdocumentbuilder.cpp:1489),
NOT in `PDFFreeTextAnnotation::draw` (draw gets only a QPainter backed by QPdfWriter
inside PDFContentStreamBuilder :1526-1534 and cannot embed Type0/FontFile2 into AP
/Resources). Touch ONLY the FreeText branches in `pdfdocumentbuilder.cpp`; never
edit `pdfannotation.cpp`. Full session record (code-path quotes, probe output,
CLI recipe): `references/form-field-appearance-streams-m14.md`.

**WS-B FreeText RTL AP (M14) — design SOURCE-VERIFIED at e667fe0a, impl pending
(2026-08-08):** additive early-return after the highlight block (:1497-1505):
`dynamic_cast<const PDFFreeTextAnnotation*>` + `getContents().isRightToLeft()`
(precedent pdfwidgettool.cpp:912) → build the AP form stream via
`PDFRTLTextEngine::create(settings, "F2")` (logical contents; fontSize/family from
`PDFAnnotationDefaultAppearance::parse(getDefaultAppearance())`, fallbacks 12/
"Helvetica"; origin 0,0) + `replaceObjectsByReferences(fontDictionary)` + `mergeTo`
(mirror :1743-1792); LTR QPainter path falls through byte-identical. GOTCHA vs
WS-A: the branch compiles into the CORE lib, which has NO `TEST_FONT_ARABIC`
compile def (those exist only on UnitTests targets) —
`src/Pdf4QtLibCore/CMakeLists.txt` has no `target_compile_definitions` at all and
needs one, or a plumbed font path (open decision at GREEN time). Full verified API
map + RED-test recipe (core-level, reopen → `getCatalog()->getPage(0)`
`->getAnnotations()` → `PDFAnnotation::parse` → walk /AP /N form /Resources /Font
for `/Subtype /Type0` + `/FontDescriptor /FontFile2`):
`references/freetext-rtl-appearance-m14.md`.

## 9. Upstream contribution feasibility (PR back to PDF4QT) — verified 2026-08-08

Use when asked to contribute the RTL work (or any albdf feature) back to upstream, or to
assess whether an upstream PR is viable. Full session record + strategy:
`references/upstream-contribution-feasibility-2026-08-08.md`; re-runnable audit probe:
`scripts/upstream-contribution-audit.sh`.

**Upstream facts (verified via GitHub API, 2026-08-08):**
- Repo is `JakubMelka/PDF4QT` — `Jacques/PDF4QT` is a 404. Default branch `master`.
- **MIT** (relicensed from LGPLv3 on 2025-04-27); README §5: contributions welcome, **no CLA**.
- No CONTRIBUTING.md; root `AGENTS.md` = Codex instructions (preserve CRLF, don't build unless asked).
- CI: `.github/workflows/ci.yml` triggers ONLY on push-to-master + workflow_dispatch — **PRs get no CI checks**; local green on current master is the only evidence.
- External PRs are rare but MERGED (nyalldawson ×4, Jan 2024, merged within days; raffaelemancuso ×3, 2023). All small fixes. Sole maintainer does direct `Issue #NNN` commits; active + responsive.
- Upstream has **zero** bidi/Arabic code and NO harfbuzz/fribidi deps (vcpkg.json = 9 minimal deps) — RTL is genuinely new value.

**Fork divergence (2026-08-08):** 153 ahead / **1,414 behind**. The fork vendored the tree
under `src/` → plain `git diff upstream/master..HEAD` is dominated by 794 renames; only
6 files are genuinely M (modified), of which exactly ONE is core-relevant:
`pdftextlayoutgenerator.cpp`.

**The RTL patch surface (measured):** 4 NEW files `pdfrtltextengine.{h,cpp}` (835 lines) +
`pdfrtltextnormalizer.{h,cpp}` (378 lines) + the layoutgenerator delta (**+~60 real lines** —
/ActualText span capture + 2 includes; the "136 insertions/80 deletions" stat is CRLF + header
noise) + `Pdf4QtLibCore/CMakeLists.txt` (+4 lines) + `vcpkg.json` (+2: harfbuzz, fribidi).
Test fonts already OFL (Noto Naskh Arabic etc.) — clean for MIT.

**License mechanics (the one hard problem):** albdf's new code is GPL-3.0-or-later (ADR-0005);
upstream is MIT. GPL cannot merge into an MIT repo, BUT the user is the sole copyright holder
of the RTL files ("albdf contributors" = user + agent work under their direction), so the
files are **dual-licensed for the PR: MIT-headed copies in the PR branch, GPL stays in albdf.**
Never let a GPL header ride into a PR (a modified MIT file with a GPL header is a license mess).
Verify authorship of every line before submitting.

**Strategy that protects the main repo:** NEVER PR from al-bdf-engine itself (GPL headers, src/
restructure, rename, 1,414-commit gap = unreviewable diff). Instead create a FRESH MIT fork of
upstream (e.g. `yolka-wiz/pdf4qt-rtl`) = patch home + PR vehicle; re-express the patch onto
fresh master; SPLIT the contribution: PR #1 = tiny /ActualText capture (~60 lines, high
acceptance odds, aligns with upstream's own text-editing work), PR #2 = engine + normalizer +
deps (biggest risk: new deps in a deliberately 9-dep project — lead with a design note), PR #3 =
GUI wiring only if #2 lands. If upstream says no, the patches live forever in the MIT fork.

**Measurement traps:**
- `git describe --tags <merge-base>` returns the FORK's own tag (e.g. 0.3.0) because the base is an ancestor of the fork tag — it says nothing about the upstream base; compare against fetched upstream tags instead.
- Blob-to-blob `git diff upstream/master:PATH src/PATH` is CRLF-noise-dominated when one side stored CRLF — always add `-w -B` (and `--ignore-space-at-eol`) and read the semantic delta; trust neither the stat nor raw output.
- `git diff --name-status` has rename detection ON by default → a tree move shows as R entries; the M (modified) list is the only thing that tells you which upstream files actually changed.

## References

- `references/upstream-contribution-feasibility-2026-08-08.md` — upstream PR feasibility
  session record (2026-08-08): upstream facts (MIT since 2025-04-27, no CLA, CI not on PRs,
  PR history), fork divergence measurements (153 ahead / 1,414 behind), the measured RTL patch
  surface (4 new files + layoutgenerator delta), GPL→MIT dual-license mechanics, the fresh-MIT-
  fork + staged-PR strategy, and the measurement traps.
- `references/gui-text-input-rtl-audit.md` — audit-only map (2026-08-07, main @
  9f5e1338) of every GUI path where a user types/pastes text that can become
  document content: 11-path table (file:line, widget class, commits-to-doc?, RTL
  today, minimal fix), the `updateAnnotationAppearanceStreams` AP choke point
  (pdfdocumentbuilder.cpp:1489-1575) where one RTL branch fixes form fields +
  FreeText, the screen-only canvas textbox tool, the stale-glyph trap in the
  edited-items dialog, form-field commit chain, and the P0/P1/P2 priority list.
  NOTE (corrected 2026-08-07): the "Find dialog" row's claim that GUI find routes
  into `PDFTextSearchEngine` is WRONG — both find entry points call the legacy
  `PDFTextLayoutStorage::find` (plain `indexOf`); see
  `references/gui-text-wiring-audit-2026-08-07.md`.
- `references/gui-search-engine-adapter-2026-08-07.md` — WS-A implementation record
  (2026-08-07, uncommitted at session end): `pdfwidgetrtlsearch.{h,cpp}` adapter
  signature + exact `performSearch` diffs for both find entry points, the verified
  Match→PDFFindResult mapping contract (painter resolves PDFCharacterPointer through
  the widget layout; getTextLayout returns a copy; createTextSelection mutates;
  empty-items trap in `PDFFindResult::operator<`), compile fixes (pdfdocumentreader.h
  include, non-const searchFlow), the `test_engineSearchSalam` unit-test recipe
  (visual-order matchedText gotcha), and the stale-core-.so link trap in build-gui.
- `references/content-editor-actualtext-r4-2026-08-07.md` — R#4 implementation record
  (2026-08-07, fix implemented + new test GREEN, suite-wide green NOT reached):
  the degradation CLI recipe, the capture/emit code shape (Item::actualText +
  performMarkedContentBegin/End overrides with nesting stack, `<actualText v=.../>`
  XML markers for per-run BDC/EMC re-emission, final EMC before ET Q), the
  per-run-vs-per-element scoping trap, the `QString::toUtf16()` native-endian trap,
  the stale-expectation pin in `test_rtlKeepsLtrIntact` (asserts the degraded `ملس`),
  and the `git stash push -- <files>` shared-worktree baseline-isolation method.
- `references/gui-text-wiring-audit-2026-08-07.md` — verified GUI↔core text wiring
  map (2026-08-07): library-only verdict (`Pdf4QtLibGui/CMakeLists.txt:99`, no
  PdfTool), the exact core APIs a GUI text feature must call (PDFRTLTextEngine::create
  + CLI fresh-stream commit pattern that bypasses the editor processor,
  PDFTextSearchEngine::search + Match→PDFFindResult mapping, getTextFromSelection
  copy path), the R#4 fix design (performMarkedContentBegin/End overrides + Item-level
  /ActualText capture + writeText re-emit), the 8-point GUI text-gap checklist, and
  stale-claims correction for `rtl-through-gui-integration.md`.
- `references/render-args-fuzz-fixes.md` — F#1/F#2 render-crash root causes, reproducer
  commands + expected exit codes, RED/GREEN test names, exact fix locations.
- `references/ci-gate-runbook.md` — verified full-gate runbook: exact commands, per-stage
  log locations, expected output lines from a green run (m10/fix-render-args).
- `references/release-0.2.0-workflow.md` — verified release recipe (albdf 0.2.0, 2026-08-07):
  version bump + hardcoded-version smoke trap, RELEASES.md/PLAN.md updates, full gate,
  deterministic tarball (build twice → identical sha256), annotated tag + push,
  `gh release create` with assets, and the fine-grained-PAT Contents:write gotcha.
- `references/feature-capability-map-2026-08-07.md` — what the vendored PDF4QT core
  already provides (PDFAnnotation create API, PDFDocumentTextFlow editing, image
  optimizer/compressor, page manipulator) vs what albdf exposes via CLI — the answer to
  "how far are we from feature X" without re-archaeologizing the engine.
- `references/compile-out-qt-module-tts-2026-08-07.md` — verified compile-out
  recipe for the Qt6::TextToSpeech blocker (commit `48d58fd8`): no-op stub
  preserving class API, `#if defined(QT_TEXTTOSPEECH_LIB)` guards on includes
  + call sites, CMake link drop, guard-macro choice, and the duplicate-include
  patch gotcha. Reusable for ANY unprovisioned Qt add-on module.
- `references/gui-restore-vendoring-2026-08-07.md` — vendoring the upstream GUI layers
  (Pdf4QtLibGui / Pdf4QtLibWidgets / Pdf4QtEditor / Pdf4QtViewer / Pdf4QtPageMaster) from
  the pinned upstream tag into `src/`, the three-pronged reattach analysis (CMake wiring /
  API compat / RTL-through-GUI), and the M12 sequencing verdict.
- `references/gui-cmake-wiring-analysis.md` — verified per-dir CMake report for the 5
  vendored GUI dirs: targets/Qt modules/link deps/include dirs, exact add_subdirectory
  wiring, the (now-resolved) Qt6::TextToSpeech configure blocker,
  INSTALL_INCLUDEDIR/QT6_INSTALL_PREFIX emptiness gotchas, build-risk order, and the
  vendored-audit verification recipe.
- `references/gui-cmake-wiring-implemented-2026-08-07.md` — M12 WS1 implementation
  record: the committed ALBDF_BUILD_GUI wiring (84c1f848), the configure command that
  succeeds, the 5 verified targets, the headless-default check, and the ninja
  target-listing verification recipe.
- `references/gui-api-compat-audit-2026-08-07.md` — verified API-compat verdict (GUI
  compiles against modified core): per-header ADDITIVE/SIGNATURE/BEHAVIORAL table, per-API
  verdicts with GUI call sites, Qt module requirements, excluded-internals check, and the
  reusable fork-compat audit method (whitespace-ignored cross-commit diffs, comm
  path-prefix trap, Qt umbrella-header classification).
- `references/gui-deps-qt-audit-ws2-2026-08-07.md` — WS2 dependency & Qt-version audit
  verdict (report-only, pre-wiring): GUI needs NO new vcpkg deps (upstream v1.6.0.0
  vcpkg.json == our 9 core deps + harfbuzz/fribidi), vendored sources compile on Qt
  6.8.2 (400-token header sweep → only TTS APIs missing, all guarded), icon.rc ignored
  on Linux, all .qrc refs exist, vendored tree pristine except the TTS divergence, plus
  the `#elif`-grep and upstream path-prefix traps.
- `references/gui-headless-smoke-2026-08-07.md` — WS4 implementation record (commit
  `1a7f2af2`): deterministic RTL fixture recipe (`add-text --rtl` on `blank.pdf`,
  sha256, visual-order fetch-text expectation), the headless smoke of Qt widget
  event-loop apps (aliveness-under-timeout open check, offscreen→xvfb fallback with
  `env -u QT_QPA_PLATFORM`, `--help` platform fallback because QApplication precedes
  the parser), stub-viewer verification method, and the stray-`Image_N.png` render
  pitfall.
- `references/gui-ci-stage-2026-08-07.md` — M12 Phase 2 record (commit `7dc95d50`):
  the `ci/run-ci.sh --gui` stage (build-gui configure + headless smoke,
  `ALBDF_CI_STAGE=gui` selector, tests-flip-OFF gotcha), the non-gating `gui` CI
  job (continue-on-error + xvfb install), the exact green transcript, and the
  check-integrity lesson for scripted ad-hoc verification (missing-dep false
  negatives, wrong self-assertions).
- `references/fine-grained-pat-permissions-2026-08-07.md` — GitHub fine-grained
  PAT two-axis permission model (repo selection × permission), the failure table
  (release create → Contents:write; PR create → GraphQL vs REST; new-repo write
  → SSH escape hatch; PATCH /user → `user` scope + `gh auth refresh` device
  flow), and the ruleset temporary-relaxation merge pattern (GET/PUT
  /rulesets/{id}, review count 0 → merge → restore, rebase→squash fallback
  when main moved).
- `references/rtl-search-visual-order-lamalef.md` — S#3 deep-dive (2026-08-07,
  `4cabbf7a`): why document-level `search()` failed on lam-alef words (query
  normalized LOGICAL, flow text VISUAL where the ligature appears as reversed
  `ال`), the `visualOrder` option fix (flow side only — never the query side,
  where `ال` is the definite article), the grep-echo measurement trap, and the
  "works in CLI but not in test" triangulation path (kept tmpdir file →
  byte-compare → char-rect probe).
- `references/appimage-packaging-2026-08-07.md` — packaging/ record: linuxdeploy +
  qt-plugin + appimagetool download URLs, the system-libs-vs-vcpkg check
  (`ldd` first — never blindly copy vcpkg `installed/*/lib`), the AppDir layout
  (.desktop at root, icon basename match, `Exec=` matches binary name), and
  headless verification notes. **Container blockers (2026-08-07, 0.3.0):**
  FUSE-less containers need `APPIMAGE_EXTRACT_AND_RUN=1`; appimagetool needs
  the `file` command installed; the SVG icon engine is a SEPARATE Debian
  package (`qt6-svg-plugins`, not `qt6-svg-dev`/`libqt6svg6`); the AppImage
  bundles only the `xcb` platform plugin, so verify under `xvfb-run` with
  `QT_QPA_PLATFORM` unset (offscreen fails inside the bundle by design).
- `references/parallel-agents-consolidation-2026-08-07.md` — M13 orchestrator
  recovery record: three parallel fix agents shared one checkout and all hit
  their caps; how the orchestrator consolidated (read all reports → build core
  with everything → triangulate the 3 test failures → apply the designed-but-
  uncommitted edits → commit per-path in logical units → full verify). Lessons:
  same-checkout parallel agents can't edit the same files; capped agents are the
  norm; verify every "done" claim yourself.
