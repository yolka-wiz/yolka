# Redact integration test suite (DB #29, LANDED 2026-08-06)

The pixel-based redaction suite is committed and green — do NOT re-author it;
extend it if the fixture/behavior changes.

- **Commits:** `3a7568b` (test suite: `src/UnitTests/tst_redacttest.cpp` +
  `src/UnitTests/CMakeLists.txt` wiring), `558a267` (docs/PROBLEMS.md
  "Redaction / render quirks" section). Fixture + generator: `4dcdb32`
  (`src/tests/fixtures/redact-annotated.pdf`,
  `src/tests/scripts/make-redact-pdf.py`). Determinism fix: `e79bc06`.
- **Target:** `UnitTestsRedact` — wired exactly like `UnitTestsPageOps`:
  `add_executable` with explicit source (no globbing),
  `target_link_libraries(... Pdf4QtLibCore Qt6::Core Qt6::Gui Qt6::Test)`,
  `target_compile_definitions(... TEST_REDACT_PDF=".../fixtures/redact-annotated.pdf")`,
  `set_target_properties` with `RUNTIME_OUTPUT_DIRECTORY`,
  `add_test(NAME UnitTestsRedact COMMAND ...)` +
  `set_tests_properties(... ENVIRONMENT "QT_QPA_PLATFORM=offscreen")` +
  `add_dependencies(UnitTestsRedact albdf)`. Full ctest: **13/13**.
- File top comment carries the fixture geometry table — keep it in sync when
  the fixture changes.

## Fixture geometry (redact-annotated.pdf, 1 page, MediaBox 612x792)

Four 24pt Helvetica lines at x=72 (baseline y in PDF space, y UP from
bottom-left):

| line | baseline y | status | /Rect |
|---|---|---|---|
| PUBLIC LINE KEEPER | 720 | public | — |
| TOP SECRET PAYLOAD ALPHA | 660 | secret | `[60 630 400 685]` |
| PUBLIC LINE OMEGA | 600 | public | — |
| CLASSIFIED BETA BLOCK | 540 | secret | `[60 510 400 565]` |

## PDF → image coordinate math (72 dpi, top-left origin)

- `image_y = page_height - pdf_y`
- A `/Rect [x1 y1 x2 y2]` (y-up) maps to image rows `[page_h - y2, page_h - y1)`:
  rect1 → x[60,400) y[107,162); rect2 → x[60,400) y[227,282).
- **24pt glyph ink sits at `image_y ∈ [baseline_img_y - 17, baseline_img_y - 1]`
  (ascenders only; descenders a few px below the baseline).** A scanline at
  the baseline or just below reads **0% black** — locate ink bands empirically
  first (row-scan for luminance < 60, group contiguous rows), then pick
  scanlines. The secret text band sits INSIDE its rect's image rows.
- Chosen scanlines: rect1 y=134, rect2 y=254 (rect middles); public1 y=64
  (band y[56,71)), public2 y=184 (band y[176,191)).

## Sampling method (C++, in tst_redacttest.cpp)

- near-black: `qGray(image.pixel(x, y)) < 60`
- `blackFraction(img, x1, x2, y) = countNearBlackRow / (x2 - x1)` — scanline
  based, not single pixels (robust to anti-aliasing edges).
- Thresholds (measured 2026-08-06, do not re-derive unless renderer changes):
  solid bar **≥ 0.95** (measured 1.000; 55/56 rows fully black — the missing
  row is an AA edge, never assert 100%); text present **∈ (0.05, 0.60)**
  (measured 0.240 / 0.218); public preservation `|out - in| < 0.03` (measured
  exactly equal).

## The five test slots

1. `redactionRegionRendersSolidBlackBar` — redact, render output AND input;
   output rect scanlines ≥ 0.95 black; **input rect scanlines must NOT be
   bars** (fixture-sanity guard — prevents a vacuous pass if the fixture were
   pre-blackened); output public scanlines ∈ (0.05, 0.60) AND ≈ input fraction
   (±0.03, content untouched).
2. `redactionPreservesPageSize` — input and output renders both 612x792.
3. `redactedOutputRoundTrip` — `info` exit 0; parse the `Page count` line,
   third whitespace token == "1".
4. `redactionOutputDeterministic` — two redact runs → sha256 identical
   (measured `5e4c0940...`; sleeps not needed since e79bc06 fixed dates).
5. `redactInvalidArguments` — missing output positional → **7**
   (`ErrorInvalidArguments`, source: `options.redactedDocument.isEmpty()`
   check in pdftoolredact.cpp), no args → 7, nonexistent input → **4**
   (`ErrorDocumentReading`) and no output file written.

## Pitfalls hit writing the suite (all real)

- **Helper returning a PATH into a function-local QTemporaryDir → QImage
  loads 0x0.** The temp dir (and PNG) is destroyed when the helper returns;
  load the `QImage` INSIDE the helper. First suite run failed exactly like
  this (`QSize(0x0)`) — a genuine RED-phase catch, not a production bug.
- **fetch-text on redacted output is EMPTY** (whole text layer baked to
  vector curves) — never assert text presence/absence on it; every such
  assertion passes vacuously. Pixel assertions only.
- clang-format gate: `clang-format --dry-run --Werror src/UnitTests/tst_*.cpp`;
  one auto-fix (`clang-format -i`) was needed for a long `runTool` call.
- Commit identity: `git -c user.name="Yolka" -c user.email="yolka@albdf.local"
  commit`; the pre-commit hook regenerates REPO_MAP.md (commit it with the
  change). Stage only your own paths.
- New traps discovered here are recorded in-repo under docs/PROBLEMS.md →
  "Redaction / render quirks (M10, DB #29)" — point agents there, don't
  duplicate.
