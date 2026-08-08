# Headless GUI smoke scaffold — RTL-through-GUI verification (albdf, 2026-08-07)

WS4 implementation record, branch `m12/gui-restore`, commit `1a7f2af2`
("test(gui): headless GUI smoke scaffold + RTL fixture"). Complements
`rtl-through-gui-integration.md` (analysis-only): this is the **built, verified**
scaffold ready for the GUI, plus the reusable headless-Qt-GUI smoke technique.

Delivered state:
- `src/tests/fixtures/gui-rtl.pdf` — 1-page deterministic RTL fixture.
- `src/tests/gui-smoke.sh` — headless smoke (bash, no deps).
- `src/tests/AGENT.md` §6.1 documents both.
- Viewer binary **NOT built yet** (expected — GUI vendored, build deferred): the
  script MUST exit 2 with "Viewer not built — run with ALBDF_BUILD_GUI=ON".

## Deterministic RTL fixture recipe (verified byte-stable)

```sh
QT_QPA_PLATFORM=offscreen src/build/bin/albdf add-text \
    src/tests/fixtures/blank.pdf /tmp/gui-rtl.pdf \
    --page 1 --x 72 --y 700 --text 'سلام' --size 24 --rtl \
    --font src/tests/fonts/NotoNaskhArabic-Regular.ttf --lang ar
sha256sum /tmp/gui-rtl.pdf
# = db787c3005a4a3275ecbbda5da0458d5fd78ad5345b465e37da9577f258f7006
cp /tmp/gui-rtl.pdf src/tests/fixtures/gui-rtl.pdf
```

- `add-text` is deterministic **with and without** `SOURCE_DATE_EPOCH` — three
  runs (two with epoch 0, one without) all produced the identical sha256; no
  timestamps (info shows fixed epoch "1/1/70"). Do not add SOURCE_DATE_EPOCH to
  the documented recipe.
- `سلام` contains lam+alef → exercises the lam-alef ligature shaping path.
- `albdf fetch-text gui-rtl.pdf` returns `مالس` — the RTL line in **visual
  order** (reversed). That is EXPECTED (matches the visual-order caveat in
  `rtl-through-gui-integration.md` §3), not a fixture bug.
- Font: `NotoNaskhArabic-Regular.ttf` (OFL-1.1, committed in
  `src/tests/fonts/`). Lang tag `ar`.

## Headless smoke of a Qt widget event-loop app (reusable technique)

The PDF4QT Viewer runs `QApplication` → `QCommandLineParser` → `mainWindow.show()`
→ `application.exec()`; it takes a positional `file` argument and has **no
`--exit` flag** (`src/Pdf4QtViewer/main.cpp`). So:

1. **Open-check = timeout-based aliveness, not exit code.**
   Start `viewer <fixture>` in background; poll `kill -0` every second for
   `GUI_SMOKE_SECONDS` (default 8). Still alive at the end ⇒ it started and
   opened the doc ⇒ `SIGTERM` it and treat a clean termination as pass.
   Self-exit with code 0 before the window is also a pass; early **nonzero**
   exit is a startup crash ⇒ fail.
2. **`--help` needs the same platform fallback as the open test.**
   In PDF4QT apps `QApplication` is constructed BEFORE the parser processes
   `--help`, so a viewer whose platform plugin refuses offscreen fails `--help`
   too. Verify `--help` under offscreen, and retry under xvfb-run before
   declaring the binary unrunnable.
3. **xvfb fallback must UNSET `QT_QPA_PLATFORM`.**
   Direct run: `QT_QPA_PLATFORM=offscreen viewer file`.
   Fallback: `env -u QT_QPA_PLATFORM xvfb-run -a viewer file` — leaving
   offscreen set makes the app stay on the (broken) offscreen plugin under the
   virtual display, so the "fallback" silently uses the same failing path.
   (Found by stub testing — see below.)
4. **Locate-first, fail-loud.** If no Viewer binary exists, exit 2 with the
   clear message; never pass silently. Candidates in order:
   `src/build-gui/bin/Pdf4QtViewer`, `src/build/bin/Pdf4QtViewer`,
   root `build-gui/bin/` / `build/bin/` (target name is `Pdf4QtViewer`; no
   OUTPUT_NAME override).
5. **Determinism guard in the harness.** Hash-check the fixture against the
   committed sha256 before running; a regenerated/mutated fixture fails loudly
   (exit 1) instead of producing a meaningless GUI run.
6. Exit-code contract of gui-smoke.sh: `0` pass, `1` a check failed, `2` viewer
   not built. Usage: `bash src/tests/gui-smoke.sh [--viewer PATH] [--fixture PATH]`,
   `GUI_SMOKE_SECONDS=N` tunes the window.

## Verifying the harness without the real GUI (stub viewers)

The script's branches are fully exercisable with fake "viewers" — no GUI build
needed:
- Healthy stub: `--help` exits 0; on a file arg `trap 'exit 0' TERM; while true;
  do sleep 1; done` (mimics the event loop).
- Offscreen-refusing stub: exit 1 with `xcb: could not connect to display`
  when `QT_QPA_PLATFORM=offscreen` and `DISPLAY` unset — forces the xvfb path.
- Crash stub: `--help` ok, then `exit 3` on open — forces the fail path.
All 6 branches (syntax / not-built / offscreen pass / xvfb fallback / hash
mismatch / crash-on-open) verified green against stubs before commit.

## Pitfall: stray `Image_N.png` from `albdf render`

`albdf render <doc> <out>` with an output path that doesn't resolve as expected
(e.g. no `.png` extension) still exits 0 but drops `Image_1.png` **next to the
input document** (observed: landed in `src/tests/fixtures/`). After any render
smoke check: `git status` and remove stray `Image_*.png`; it will not be part of
your commit and pollutes the fixtures dir.

## Wiring note

Not wired into CTest/CI yet — the GUI isn't built. When the GUI lands
(`ALBDF_BUILD_GUI=ON`, viewer at `src/build-gui/bin/Pdf4QtViewer`), the script
self-activates; wire it as a CTest target then (see `src/UnitTests/AGENT.md`
runTool/QProcess pattern for the CLI analog).
