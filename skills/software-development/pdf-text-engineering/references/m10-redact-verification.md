# albdf redact verification (M10, DB #29) — findings & status

Session date: 2026-08-06. Worktree: `/home/agent/workspace/wt-core-redaction`,
branch `m10/core-redaction` (main checkout `/home/agent/workspace/al-bdf-engine`
must NOT be edited). Task: verify `albdf redact`, TDD integration test, full
suite green, determinism + round-trip.

## Status at session end (follow-up session 2, 2026-08-06)

- Build blocker RESOLVED: fix commit `0a655ad` (branch `m10/core-redaction`,
  64-bit Options class) builds clean; incremental `cmake --build` exit 0;
  binary present at `src/build/bin/albdf`.
- **Smoke VERIFIED with real output** (all exit codes + hashes below).
- Fixture created: `src/tests/scripts/make-redact-pdf.py` →
  `src/tests/fixtures/redact-annotated.pdf` (byte-deterministic: two
  generations → sha256 `9d4833be…`). NOT yet committed.
- **NEW BLOCKER (determinism bug, evidence captured, fix not applied):**
  `albdf redact` output is non-deterministic — see §5. Needs orchestrator
  decision (fix is in vendored Pdf4QtLibCore builder, outside the plan's
  `src/PdfTool/` scope).
- Test file `tst_redacttest.cpp` NOT yet written; no commits made; full ctest
  not re-run (session hit tool-call cap after the determinism investigation).

## 1. The redact command: real CLI surface (verified from source)

`src/PdfTool/pdftoolredact.{h,cpp}` — upstream-vendored, static-registered
(`static PDFToolRedact s_redactApplication;`), `Command` = `"redact"`,
`getOptionsFlags() = ConsoleFormat | OpenDocument | ColorManagementSystem |
Redact`. The `Redact` option group (in `pdftoolabstractapplication.cpp`)
adds only:

- positional `redacteddocument` (output filename) — so usage is
  `albdf redact <input.pdf> <output.pdf>`
- `--redact-copy-title` / `--redact-copy-metadata` / `--redact-copy-outline`

**There is NO `--page`, `--rect-*`, or selection flag.** The plan's smoke
command (`redact multipage.pdf out.pdf --page 1`) is invalid; unknown options
die in `QCommandLineParser::process()` (main.cpp) with a non-zero exit.

### How regions work (verified from pdfredact.cpp)

`PDFRedact::perform()` rebuilds the whole document page by page:

1. For each page, iterate `page->getAnnotations()`; keep only
   `AnnotationType::Redact`; union `redactAnnotation->getRedactionRegion()
   .getPath()` into one `QPainterPath`.
2. `compiledPage.redact(redactPath, matrix, Qt::black)` — subtracts the
   (inverse-transformed) region from every `DrawPath` instruction's path
   (glyph outlines ARE paths, so text inside the region is cut), then
   overpaints a black fill.
3. Re-serialize via `PDFDocumentBuilder` + `PDFPageContentStreamBuilder`.

`getRedactionRegion()` is parsed in `pdfannotation.cpp` from `/QuadPoints`;
`PDFAnnotation::parseQuadrilaterals` falls back to the annotation `/Rect`
when QuadPoints is absent, so a minimal annotation dict is:

```
<< /Type /Annot /Subtype /Redact /Rect [60 630 400 680] >>
```

### VERIFIED quirk: the output text layer is gone entirely

`PDFContentStreamBuilder` (pdfdocumentbuilder.h:263-268) wraps
`QPdfWriter` + `QBuffer`; `PDFPrecompiledPage::draw()` emits even text glyphs
via `painter->drawPath(data.path)` (pdfpainter.cpp:550-560). QPdfWriter
serializes paths as vector curves, NOT text operators. **CONFIRMED by
execution (real output):** `fetch-text` on the redacted output returns
NOTHING (blank), even though the input's 4 lines all extract. So:

- assert the SOURCE fixture's fetch-text contains the region text (proves the
  fixture is extractable), and the OUTPUT's fetch-text does not;
- pin "redaction actually did something" with **render-pixel evidence**
  (works; measured values below), NOT with fetch-text diff of public lines
  (a "public line survives" assertion fails by design).

### VERIFIED smoke results (session 2, real output)

Fixture `redact-annotated.pdf`: 1 page, 4 Helvetica 24pt lines at x=72 —
PUBLIC LINE KEEPER (y=720), TOP SECRET PAYLOAD ALPHA (y=660, redacted),
PUBLIC LINE OMEGA (y=600), CLASSIFIED BETA BLOCK (y=540, redacted). Two
Redact annotations, `/Rect` only (no QuadPoints — exercises the
parseQuadrilaterals fallback): `[60 630 400 685]` and `[60 510 400 565]`.

- `fetch-text` BEFORE: all 4 lines present, exit 0.
- `albdf redact <fixture> /tmp/redacted.pdf` → exit 0, output 6,998 bytes.
- `fetch-text` AFTER → empty output, exit 0 (vector baking confirmed).
- Render both at 72 dpi (612x792 px): region1/region2 near-black fraction
  input **5.4%/5.3%** (text ink only) → output **100.0%/100.0%** (solid black
  fill). Public-line band on output: 6.2% black (content outside regions
  still renders). Sampled differing pixels in/out: 2258 (page rebuilt).
- Round-trip: `info` on redacted output → exit 0, page count 1.
- Determinism: same-second double run → sha256 identical
  (`19f8bdd0…`); **3 s apart → DIFFERENT hashes** (`f92d1342…` vs
  `5b7d87a0…`) — see §5.

Fixture generation (committed generator + fixture pending): object layout
Catalog=1, Pages=2 (placeholder), Contents=3, Font=4, Resources=5, Page=6
(`/Annots [7 0 R 8 0 R]`), annotations 7-8. Determinism proof: two
generations → identical sha256 `9d4833be…`.

## 5. Determinism bug: builder stamps wall-clock time (VERIFIED, OPEN)

Byte-diff of the two sleep-separated redact outputs: first difference at
byte 6162, and the ONLY differing bytes are the `/Info` dict date strings:

```
A: << /Producer (PDF4QT 0.1.0) /CreationDate (D:20260806144439) /ModDate (D:20260806144439) >>
B: << /Producer (PDF4QT 0.1.0) /CreationDate (D:20260806144442) /ModDate (D:20260806144442) >>
```

Root cause: `PDFDocumentBuilder::createTrailerDictionary`
(pdfdocumentbuilder.cpp:5375-5404) emits `WrapCurrentDateTime()` for
`CreationDate`/`ModDate` (line 5383-5388) whenever a blank document is
created — which `PDFRedact::perform()` does via `builder.createDocument()`
(pdfredact.cpp:50-51). The writer's `write(..., true)` third arg is
`safeWrite` (atomic rename), NOT metadata — not a contributor.
`pdftoolunite.cpp:78` uses the same builder path, so `unite` is equally
non-deterministic. `QDateTime::currentDateTime()` appears ONLY in
pdfdocumentbuilder.cpp within Pdf4QtLibCore (verified by grep).

Consequence for tests: a back-to-back determinism assertion passes by luck
inside one second — the test is FLAKY pre-fix. Detection recipe: run the
command twice with `sleep 3` between, compare sha256, byte-diff to locate.

Proposed fix (NOT applied; needs orchestrator sign-off — it touches vendored
Pdf4QtLibCore, while the plan limits code changes to `src/PdfTool/`): make
`createTrailerDictionary` deterministic (drop the date keys or use a fixed
date) so every builder-based command (redact, unite) is byte-stable. This is
required to meet the task's determinism gate and the repo's "determinism
above all" contract.

## 2. Build blocker: QFlags 32-bit overflow (verified root cause)

Exact error (first build attempt, before any edits):

```
/usr/include/x86_64-linux-gnu/qt6/QtCore/qflags.h:54:33: error: static assertion failed:
QFlags uses an int as storage, so an enum with underlying long long will overflow.
    static_assert((sizeof(Enum) <= sizeof(int)),
```

Chain: `pdftoolabstractapplication.h` `enum Option` has 34 entries. Upstream
vendored (commit 6bf5047) 26 bits (0x00000001..0x02000000). The fork added 8:
`DeleteObject` 0x04000000, `AddText` 0x08000000, `SearchText` 0x10000000,
`FormFill` 0x20000000, `Sign` 0x40000000, `Rotate` 0x80000000 (all fit an
`unsigned int` underlying type — 4 bytes, assert passes), then page-ops
commit **4402b1c** added `MovePage = 0x100000000` and `DeletePage =
0x200000000` → underlying type 8 bytes → assert fires.

- System Qt here: **6.8.2** (`qmake6 -query QT_VERSION`). CI pins Qt 6.8.*
  (`.github/workflows/ci.yml` + `.github/actions/setup-toolchain/action.yml`).
- Qt ≥ 6.9 supports 64-bit QFlags ("Since Qt 6.9, QFlags supports 64-bit
  enumerations" — Qt docs), but the project floor is Qt 6.8 (root
  AGENTS.md §5), so bumping Qt is not an option.
- Upstream PDF4QT master still has only 26 options — no upstream pattern to
  follow; this is purely fork-made.
- The main checkout's `build/bin/albdf` is dated BEFORE 4402b1c's commit time
  → the page-ops milestone (rotate/move-page/delete-page) NEVER compiled on
  this toolchain, yet was merged ("already compiled" claims were false).
  Always compare binary mtime vs `git log --format=%ci <commit>`.

### Fix design (applied to working tree, NOT verified/committed)

Replace `Q_DECLARE_FLAGS(Options, Option)` + `Q_DECLARE_OPERATORS_FOR_FLAGS`
with a minimal 64-bit `Options` class in the same header. Audited all usages
(`grep -rn "getOptionsFlags\|Options" PdfTool/`): only `testFlag(X)`,
`return A | B | C;` construction, and `|/&/~` — no QVariant/meta-type use, no
comparisons beyond `==`. So a drop-in class needs: default ctor, implicit
ctor from `Option`, `testFlag`, `operator|=`/`|`, `operator&=`/`&`,
`operator~`, `operator==`/`!=`, `explicit operator bool`, plus free
`operator|(Option, Option)` (etc.) replacing the macro. Keep ALL 34 values
unchanged. See the applied diff in the worktree's
`src/PdfTool/pdftoolabstractapplication.h` (uncommitted).

## 3. Build/test commands that work on this machine

```
export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg   # NOT /workspace/vcpkg
cd /home/agent/workspace/wt-core-redaction/src
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake \
  -DALBDF_BUILD_TESTS=ON        # configure OK (5.4s); deps resolve from vcpkg_installed
cmake --build build -j$(nproc)
QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure
```

Qt comes from the SYSTEM (`/usr/lib/x86_64-linux-gnu/cmake/Qt6Core`, 6.8.2) —
vcpkg manifest does NOT include qtbase. Fixture `multipage.pdf` = 5 pages,
"<MULTIPAGE PAGE <N>>" text at `BT /F1 24 Tf 72 720 Td (...) Tj ET` + one
vector shape per page, 612x792.

## 4. Planned next steps (for the follow-up session 3)

1. **Orchestrator decision on the determinism fix (§5)** — the gate
   "identical output on re-run" is unmet without touching
   `PDFDocumentBuilder::createTrailerDictionary` (vendored library code).
   Options: (a) approve the deterministic-dates fix in the builder
   (recommended — also fixes `unite`), (b) normalize dates in the test
   (weak — violates the repo contract). Do not proceed to determinism
   assertions before this.
2. Commit fixture: `test(cli): add Redact-annotated fixture (DB #29)` —
   `src/tests/scripts/make-redact-pdf.py` + `src/tests/fixtures/redact-annotated.pdf`
   (sha256 `9d4833be…`), register in smoke.sh PAGES/TEXT tables.
3. TDD `tst_redacttest.cpp` reusing `runTool()` from `tst_pageopstest.cpp`
   (QTEST_GUILESS_MAIN, QTemporaryDir, sha256 for determinism,
   `#include "tst_redacttest.moc"`); wire `UnitTestsRedact` into
   `src/UnitTests/CMakeLists.txt` (add_test + add_dependencies(albdf) +
   offscreen ENV). Test design per VERIFIED reality: region strings absent
   from output fetch-text; render-pixel black-fraction ≈ 100% in regions vs
   ~5% input and non-black outside; `info` round-trip exit 0; determinism
   via sha256. RED commit first, then fix/GREEN commit (the only genuine RED
   is determinism — the removal itself already works upstream).
4. Full ctest green, commit SHAs, then report; do NOT close DB #29 without
   passing-test + git-log evidence.
