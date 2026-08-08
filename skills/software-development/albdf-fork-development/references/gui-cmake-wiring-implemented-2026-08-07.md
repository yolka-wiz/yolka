# GUI CMake wiring — implemented & configure-verified (M12 WS1, commit 84c1f848)

Implementation record for the `ALBDF_BUILD_GUI` wiring (supersedes the analysis-only
state; see `gui-cmake-wiring-analysis.md` for the per-dir target/module breakdown).
Configure with the GUI flag is VERIFIED; the full GUI build has NOT been run yet (too
slow — that is the next milestone's job).

## Committed wiring (src/CMakeLists.txt, commit 84c1f848)

- `find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Xml Svg Test Widgets PrintSupport Concurrent)`
- `set(CMAKE_INCLUDE_CURRENT_DIR ON)` (needed by vendored GUI dirs for self-includes;
  upstream gets it via `qt_standard_project_setup`, which we don't use)
- `option(ALBDF_BUILD_GUI "Build the optional vendored PDF4QT GUI libs + apps" OFF)`
- `if(ALBDF_BUILD_GUI)` → `add_subdirectory` order:
  `Pdf4QtLibWidgets`, `Pdf4QtLibGui`, `Pdf4QtEditor`, `Pdf4QtViewer`, `Pdf4QtPageMaster`
  (LibWidgets BEFORE LibGui — LibGui links it by name). EditorPlugins and
  `Pdf4QtLibGui/main.cpp` intentionally NOT wired.
- **TextToSpeech must NOT be in find_package** — patched out at 48d58fd8 (stub +
  guards + link-line drop). Re-adding it fails configure on this box (no
  qt6-texttospeech-dev) and recompiles dead code.

## Configure command that works (from repo root)

```bash
export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg
cmake -S src -B src/build-gui -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake -DALBDF_BUILD_GUI=ON
```

→ exit 0, "Configuring done (3.9s)". Build dir name `build-gui` is ALREADY covered by
the root `.gitignore` `build-*/` pattern — no .gitignore edit needed. Qt warnings
"Could NOT find XKB/Cups" are optional-feature probes, identical in the baseline
headless build — not GUI regressions.

## Verify the 5 targets (no build needed)

```bash
ninja -C src/build-gui -t targets all | grep -E 'Pdf4Qt(LibWidgets|LibGui|Editor|Viewer|PageMaster)' | grep -E ':( phony| CXX_)'
```

Expected: phony targets `Pdf4QtLibWidgets`, `Pdf4QtLibGui`, `Pdf4QtEditor`,
`Pdf4QtViewer`, `Pdf4QtPageMaster`; `lib/libPdf4QtLibWidgets.so.1.6.0.0` +
`lib/libPdf4QtLibGui.so.1.6.0.0` (SHARED linkers); `bin/Pdf4QtEditor`,
`bin/Pdf4QtViewer`, `bin/Pdf4QtPageMaster` (EXECUTABLE linkers). AUTOMOC/AUTOUIC/
AUTORCC artifacts (`ui_*.h` per dialog, `qrc_*.cpp`, `_autogen` targets) also prove the
dirs were picked up.

## Headless-default check (contract evidence)

```bash
cmake -S src -B src/build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake -DALBDF_BUILD_TESTS=ON
ninja -C src/build -t targets all | grep -c 'Pdf4Qt\(LibWidgets\|LibGui\|Editor\|Viewer\|PageMaster\): phony'   # == 0
```

GUI-OFF configure succeeds with 0 GUI targets → the optional flag genuinely preserves
the headless contract (ADR-0002).

## Doc contract updates that rode along (same commit)

- root `AGENTS.md` §1: "What we do NOT build by default" (was: "do NOT build (yet): any GUI")
- `src/AGENT.md`: conventions bullet, dir-layout rows for the 5 GUI dirs, build-system
  bullet, Qt-module-scope pitfall
- `docs/decisions/0002-no-gui-in-v1.md`: Addendum (M12) — decision stands, optional target
- `REPO_MAP.md` regenerated via `python3 scripts/gen-repo-map.py` BEFORE committing;
  the pre-commit hook then passes cleanly (markdown gate) — no `--no-verify` needed.

## Pitfalls learned

- **Stage specific paths, never `git add -A`/`git add .`, in this multi-agent repo:**
  parallel agents drop untracked files mid-task (this session:
  `src/tests/fixtures/gui-rtl.pdf`, `src/tests/gui-smoke.sh` appeared while working).
  `git add <my files>` only; leave strangers' untracked files alone.
- Configure-only is the cheap wiring smoke test: seconds with a warm vcpkg cache, while
  a full GUI build is far too slow for a WS1-style verify step. Don't build to prove
  wiring — use `ninja -t targets`.
