# Vendoring upstream GUI/app dirs into a Qt fork (M12 case study, 2026-08-07)

End-to-end recipe for bringing an upstream Qt project's GUI layers (apps +
widget libs) into a fork that so far only built the core/CLI — proven on
albdf (PDF4QT v1.6.0.0 → `Pdf4QtLibGui`, `Pdf4QtLibWidgets`, `Pdf4QtEditor`,
`Pdf4QtViewer`, `Pdf4QtPageMaster`; 358 files, 62 cpp).

## Why this works

PDF4QT's GUI is layered Core ← LibWidgets ← LibGui ← apps, all consuming the
same library API. If the fork's core changes are ADDITIVE (headers only,
signature-identical), the vendored GUI compiles against the modified core on
the FIRST real build — the API-compat audit pays off.

## Steps (in order)

1. **Pin the upstream commit/tag** that matches the fork base:
   ```bash
   git remote add upstream https://github.com/<owner>/<upstream>.git
   git fetch upstream --tags
   git rev-parse v<tag>            # fork's vendored PDF4QT_VERSION tells you the tag
   ```
2. **Vendor the dirs at the pinned tag** (not latest — upstream moves on):
   ```bash
   mkdir -p /tmp/upstream-gui
   for d in Pdf4QtLibGui Pdf4QtLibWidgets Pdf4QtEditor Pdf4QtViewer Pdf4QtPageMaster; do
     git archive v<tag> "$d" | tar -x -C /tmp/upstream-gui
   done
   cp -r /tmp/upstream-gui/Pdf4Qt* src/
   git add src/Pdf4Qt* && git commit -m "vendor(upstream): add PDF4QT v<tag> GUI layers"
   ```
   Keep out: plugin dirs (runtime-loaded, degrade gracefully), generators,
   tools, other apps — unless the task needs them.
3. **Run a 3-way parallel analysis BEFORE the build** (one subagent each):
   - CMake wiring: read each dir's CMakeLists — targets, Qt modules,
     link deps, install rules, parent-variable assumptions.
   - API compatibility: diff the fork's modified core headers vs upstream
     tag; classify ADDITIVE / SIGNATURE CHANGE / BEHAVIORAL; grep GUI call
     sites for every changed function.
   - RTL/integration: where the GUI writes/renders/searches text, whether
     the fork's engine changes are inherited automatically.
   Verify each report independently (spot-check the diffs, the includes,
   the Qt module availability).
4. **Wire behind a gate, keeping the headless default**:
   ```cmake
   find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Xml Svg Test Widgets PrintSupport Concurrent)
   set(CMAKE_INCLUDE_CURRENT_DIR ON)
   option(ALBDF_BUILD_GUI "Build the optional vendored GUI" OFF)
   if(ALBDF_BUILD_GUI)
     add_subdirectory(Pdf4QtLibWidgets)   # order matters: libs before apps
     add_subdirectory(Pdf4QtLibGui)
     add_subdirectory(Pdf4QtEditor)
     add_subdirectory(Pdf4QtViewer)
     add_subdirectory(Pdf4QtPageMaster)
   endif()
   ```
   Configure only (`cmake -S src -B src/build-gui -DALBDF_BUILD_GUI=ON`) and
   confirm the targets appear in build.ninja BEFORE the full build.
5. **Compile out unprovisioned Qt modules** (see SKILL.md pitfall 17 stub
   pattern) — e.g. Qt6TextToSpeech absent → no-op stub + `QT_TEXTTOSPEECH_LIB`
   guards + drop module from CMake link.
6. **Add DIRECTORY-level format-gate exclusions** for the vendored dirs
   (see SKILL.md pitfall 13) — CI's format job is the fast canary for
   missing exclusions.
7. **Build + smoke + regression**: `cmake --build src/build-gui`,
   headless smoke (offscreen → xvfb fallback), and the core suite must stay
   green (`ctest --test-dir src/build`).

## Verification evidence (M12, all green)

- 270/270 targets built, ZERO fix commits — API-compat audit validated
- Headless smoke: viewer opens RTL fixture offscreen, survives 8s, clean SIGTERM
- Core regression: 14/14 ctest
- Viewer links the fork's modified libPdf4QtLibCore (verify with `ldd`, not
  assumptions)

## Pitfalls hit

- **`git archive` is the clean extractor** — preserves exact tag content
  without submodule/CRLF surprises.
- **Order of add_subdirectory matters**: LibWidgets must precede LibGui
  (LibGui links LibWidgets by name). Apps after both.
- **PageMaster does NOT link LibGui** — it's a standalone app on
  LibWidgets+Core; don't force the dependency.
- **GUI apps have no headless text-extraction flag** — the v1.6.0.0 CLI
  surface (`--help` of all 3 apps) has no fetch-text/export. RTL round-trip
  verification goes through the core CLI on the fixture instead.
- **A subagent's branch switch can steal your commit** — check
  `git branch --show-current` before committing orchestrator-level fixes
  (see SKILL.md pitfall 13 branch-mixup trap).
