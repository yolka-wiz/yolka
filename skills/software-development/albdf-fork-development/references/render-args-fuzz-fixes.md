# F#1/F#2 render-argument fuzz crashes (DB #32/#33, milestone m10) — worked example

Full worked example of the pitfalls in SKILL.md. Reproducers saved by the fuzz harness at
`/tmp/fuzz-final/fail/cli_render_{page0,huge_last,huge_dpi}.{cmd,log,pdf}`; the fixture is
`src/tests/fixtures/multipage.pdf` (5 pages, 612x792 pt Letter).

## F#1 — `--page-first 0` / `--page-last 999999999` → SIGABRT 134

**Symptom (stderr):**
```
Qt Concurrent has caught an exception thrown from a worker thread.
terminate called after throwing an instance of 'std::out_of_range'
  what():  vector::_M_range_check: __n (which is 18446744073709551615) >= this->size() (which is 5)
```

**Root cause chain:**
1. `PDFToolOptions::getPageRange(pageCount, ...)` → `PDFClosedIntervalSet::parse(1, pageCount,
   "0-1", &err)` — `first`/`last` are used ONLY as defaults for open-ended ranges; explicit
   out-of-range bounds were accepted silently (the header doc *claims* they are rejected).
2. `0-1` unfolds to {0,1}; the zero-based conversion does `--index` → {-1, 0}.
3. `PDFRasterizerPool` worker calls `PDFCatalog::getPage(index)` → `m_pages.at(index)` throws
   `std::out_of_range` inside a Qt Concurrent worker → Qt Concurrent cannot propagate
   exceptions → `std::terminate` → SIGABRT (rc 134). `1-999999999` also unfolds a ~1e9-entry
   vector (8 GB) before crashing on page index 5.

**Fix:** in `PDFClosedIntervalSet::parse` (src/Pdf4QtLibCore/sources/pdfutils.cpp) add
`if (lower < first || upper > last) { error = "...is out of the range [%1, %2]."; break; }`
(and the same for single values). Every caller already checks the parse error and returns
`ErrorInvalidArguments` (7): render, fetch-text, fetch-images, separate, audiobook,
delete-page, search-text, etc. Result: `Closed interval [0, 1] is out of the range [1, 5].` →
rc 7, instant, no 8 GB unfold.

## F#2 — `--image-res-dpi 999999` → never completes (HANG 124)

**Root cause:** the 72..6000 DPI clamp EXISTS at CLI parse time
(`pdftoolabstractapplication.cpp`, `qBound(72, dpi, 6000)` + "Dpi must be in range from 72 to
6000. Defaulting to 6000." — the fuzz log DOES contain this line). The bound is insufficient:
6000 dpi × 612x792 pt = 51000x66000 px ≈ 3.4 GP ≈ 13.5 GB RGBA → OOM thrash/hang. On a box
with a 10 GB `ulimit -v`, the allocation failed and it exited 0 with a buried
"Image is empty" error — broken either way.

**Fix:** in `PDFToolRenderBase::execute` (src/PdfTool/pdftoolrender.cpp) factor the image-size
computation into a shared `imageSizeGetter` lambda (single source of truth, also used by the
rasterizer) and, before any allocation, reject any selected page whose computed size exceeds
`PDFPageImageExportSettings::getMaxPixelResolution()` (16384) per dimension — the same
envelope pixel-resolution mode already enforces. Message: `Rendered image size 51000x66000
for page 1 exceeds the maximum supported size 16384x16384. Use a lower --image-res-dpi
value.` → rc 7, instant. This also protects the `benchmark` command (shares execute()).

## Regression suite (src/UnitTests/tst_rendertest.cpp, target UnitTestsRender)

Tests: `renderPageFirstZeroFailsWithErrorCode`, `renderPageLastHugeFailsWithErrorCode`
(assert NormalExit + rc 7), `renderHugeDpiDoesNotHang` (bounded waitForFinished(60 s) +
finishedInTime + NormalExit + rc 7), `renderValidSinglePagePositiveControl` (rc 0 + non-empty
PNG), `renderOutputIsByteDeterministic` (SHA-256 of Image_1.png across two runs).

RED evidence: 4 passed / 3 failed — page0 `CrashExit`, huge-last `CrashExit`, huge-dpi
`finishedInTime=FALSE` (60 s hang); positive control + determinism passed. 64 s runtime.
GREEN: 7/7 in 245 ms. Full ctest: 13/13.

## Reproducer verification (post-fix rc values)

```bash
B=build/bin/albdf; P=$PWD/tests/fixtures/multipage.pdf   # run from src/
QT_QPA_PLATFORM=offscreen $B render $P --page-first 0 --page-last 1 --image-format png --image-res-dpi 72 --image-output-dir /tmp/g0; echo rc=$?   # 7
QT_QPA_PLATFORM=offscreen $B render $P --page-first 1 --page-last 999999999 --image-format png --image-res-dpi 72 --image-output-dir /tmp/g1; echo rc=$?  # 7
QT_QPA_PLATFORM=offscreen $B render $P --page-first 1 --page-last 1 --image-format png --image-res-dpi 999999 --image-output-dir /tmp/g2; echo rc=$?  # 7
```

## Also changed

- `ci/run-ci.sh`: added `pdfutils.cpp` + `pdftoolrender.cpp` to the format-gate exclusion
  list (pristine vendored upstream files; see SKILL.md §3).
- Commits: RED `1e82591` (test), GREEN was prepared but NOT committed at session end.
