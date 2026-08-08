# GUI restore: vendoring upstream PDF4QT GUI layers + reattach analysis

Date: 2026-08-07. Branch: `m12/gui-restore` (commit `e3d63287`).
Status: analysis phase — GUI vendored into `src/` but NOT wired into CMake yet.

## Why this matters

The user's product feature list (click-to-edit text, image move/resize, page
thumbnail panel, highlight/comment/stamp/drawing tools, zoom presets) is a GUI
product spec. PDF4QT upstream ALREADY ships that GUI (`Pdf4QtEditor`,
`Pdf4QtViewer`, `Pdf4QtPageMaster` on top of `Pdf4QtLibGui`/`Pdf4QtLibWidgets`);
ADR-0001/0002 stripped it from the fork. The cheapest route to the feature list
is to reattach the upstream GUI to our (RTL-extended) core — not to rebuild the
GUI headless-first. The core is GUI-agnostic: `Pdf4QtLibCore` links only
Qt6::Core/Gui/Xml/Svg (no QtWidgets), and `PDFWidgetSnapshot` is a QPixmap
grabber, not a QWidget — so reattaching does not drag GUI state into the headless
library.

## Decision: SAME repo, not a separate project (user asked, 2026-08-07)

Verdict: keep the GUI in the al-bdf-engine repo (vendored under `src/`, behind
`ALBDF_BUILD_GUI=ON`). The deciding fact: the GUI is **vendored upstream code
consuming our modified core** — it has no independent lifecycle, roadmap, or
user base, so a separate repo would be a vendored copy with one consumer and
zero independent evolution. Upstream PDF4QT itself keeps core + GUI + apps in
one repo (the proven matched-pair pattern). Reasons that would CHANGE the
verdict (split triggers, none true today): we author our own GUI from scratch;
third parties consume the core as a library (then core deserves its own repo +
semver); repo size/CI time becomes a real pain (3.9 MB — no). Keep the seam
clean in-repo: GUI never depends on the CLI (links core only), core stays
GUI-agnostic, `ALBDF_BUILD_GUI` gate preserves headless default, GUI CI job
non-gating.

## Vendoring recipe (verified)

```bash
# 1. Add upstream remote + fetch (tags carry the version pins)
git remote add upstream https://github.com/JakubMelka/PDF4QT.git
git fetch upstream            # pulls all tags incl. v1.6.0.0

# 2. Identify the fork-base tag: our vendored core says PDF4QT_VERSION 1.6.0.0
#    (src/CMakeLists.txt keeps it for upstream compatibility). Use git show
#    <tag>:CMakeLists.txt to confirm the version.
git rev-parse v1.6.0.0        # tags resolve WITHOUT the upstream/ prefix

# 3. Extract GUI dirs at the pinned tag — git archive avoids submodule/CI noise
mkdir -p /tmp/upstream-gui
for d in Pdf4QtLibGui Pdf4QtLibWidgets Pdf4QtEditor Pdf4QtViewer Pdf4QtPageMaster; do
  git archive v1.6.0.0 "$d" | tar -x -C /tmp/upstream-gui
done
# 62 cpp files, ~3.9 MB total (LibGui 26 cpp, LibWidgets 22 cpp, PageMaster 12)

# 4. Copy into src/ and commit as a vendor commit
cp -r /tmp/upstream-gui/* src/
git add src/Pdf4QtLibGui src/Pdf4QtLibWidgets src/Pdf4QtEditor src/Pdf4QtViewer src/Pdf4QtPageMaster
git commit -m "vendor(upstream): add PDF4QT v1.6.0.0 GUI layers ..."

# 5. Deliberately exclude: CodeGenerator, JBIG2_Viewer, PdfExampleGenerator,
#    Pdf4QtDiff, Pdf4QtLaunchPad, Pdf4QtEditorPlugins (initial scope)
```

## Facts established (independent verification, before dispatching agents)

- **Dependency chain:** `Pdf4QtLibWidgets` → `Pdf4QtLibGui` → apps
  (Editor/Viewer/PageMaster), all sitting on `Pdf4QtLibCore`.
- **vcpkg deps:** identical to ours — upstream `tbb, openssl, lcms, zlib,
  openjpeg, freetype, libjpeg-turbo, libpng, blend2d`; albdf adds only
  `harfbuzz, fribidi` for RTL. GUI needs NO new vcpkg packages.
- **Qt modules:** GUI uses QWidget/QFontComboBox/QColorDialog/etc → needs
  **Qt6::Widgets** (a new build dep for the GUI targets only; core stays
  headless). Offscreen platform still works for GUI tests.
- **Includes are self-contained:** GUI `#include "pdf..."` headers resolve
  inside the GUI dirs (pdfwidgetutils.h, pdfdrawwidget.h, pdfcompiler.h...) or
  the core (pdfdbgheap.h, pdfpainterutils.h, pdfdocumentbuilder.h, pdfcms.h) —
  all present in the fork.
- **API compat (head diff, not build):** our core header changes
  (pdftextlayout.h, pdftextsearchengine.h, pdfutils.h, pdfrecognizetext.h,
  pdfrtltextengine.h, pdfrtltextnormalizer.h, pdftextlayoutgenerator.h) are
  ADDITIVE or cosmetic (license headers, includes, formatting) — no signature
  removals. The one behavioral change (`PDFClosedIntervalSet::parse` now
  rejects out-of-range intervals, the F#1 fix) is compatible: GUI callers pass
  valid ranges and already handle the error-string return.

## Three-pronged analysis (the subagent split that works)

Dispatch 3 parallel leaf agents, each READ-ONLY (analyze, do not modify/build):

1. **CMake wiring** — for each of the 5 dirs: target name/type, Qt components,
   link deps, include dirs, install rules/.qrc/.ts, parent-build assumptions;
   output the exact `add_subdirectory` wiring + missing variables for
   `src/CMakeLists.txt`, a dependency graph, and an honest build-risk list.
2. **API compatibility** — diff each modified core header against upstream
   (git diff fork-base HEAD) and classify ADDITIVE / SIGNATURE CHANGE /
   BEHAVIORAL; grep GUI call sites of changed functions
   (`PDFClosedIntervalSet::parse`, PDFRecognizeText, PDFTextLayout,
   search-engine methods); per-API verdict table.
3. **RTL-through-GUI** — where the GUI creates/modifies text (which
   text-editing dialog → PDFDocumentTextFlow / content-editor path), whether
   the /ActualText overlay is picked up by the GUI renderer automatically,
   whether the GUI search uses our RTL-aware PDFTextSearchEngine, and where
   R#4 (content-editor drops /ActualText on mixed add-text) would surface.

## Assessment summary (what the agents report should confirm)

- Reattach effort ~1.5–2 weeks: re-add dirs + CMake wiring (3–5 days), RTL
  verification through the GUI (1–2 days), differentiator wiring (2–3 days).
- Feature list is ~90% upstream's existing UI — thumbnails, zoom presets,
  click-to-edit, image ops, annotation/drawing/stamp tools, page reorder.
- M12 = restore GUI on `m12/gui-restore`; M13 = R#4 + CLI exposure of the
  annotation suite; M14 = text editing + find/replace pipeline.
- Risks: upstream GUI code is NOT in our repo until vendored (pin the commit —
  don't chase latest, upstream targets Qt 6.9+ now); behavioral drift between
  our fixed core and upstream GUI; QtWidgets breaks the headless-test contract
  for GUI targets (keep GUI a separate target, test with offscreen).
