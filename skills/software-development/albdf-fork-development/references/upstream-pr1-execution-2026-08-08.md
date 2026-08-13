# Upstream PR #1 execution record (2026-08-08) — pdf4qt-rtl vehicle + port + build + test

Execution companion to `upstream-contribution-feasibility-2026-08-08.md` (the strategy) and
`upstream-sync-audit-2026-08-08.md` (no-ancestry fact). This file = what actually ran.

## 1. Vehicle creation (MIT fork = patch home + PR vehicle)

- Fork via API: `gh api repos/JakubMelka/PDF4QT/forks -X POST` → creates `yolka-wiz/PDF4QT`
  under the authed user (classic token with `repo` scope works; fine-grained PAT may need
  admin/repo-creation scope — SSH escape hatch per `fine-grained-pat-permissions-2026-08-07.md`).
- **Rename keeps the fork network:** `gh api repos/yolka-wiz/PDF4QT -X PATCH -f name=pdf4qt-rtl`
  → `yolka-wiz/pdf4qt-rtl` with `fork=true`, `parent=JakubMelka/PDF4QT` — PRs to upstream still
  work. A non-fork repo CANNOT PR to upstream (no fork relationship).
- Isolated checkout: `git clone git@github.com:yolka-wiz/pdf4qt-rtl.git` +
  `git remote add upstream https://github.com/JakubMelka/PDF4QT.git`. Never mix with
  al-bdf-engine (GPL headers, src/ vendoring, no ancestry).

## 2. Port recipe (fork deltas → fresh master), CRLF traps

- Semantic delta extraction: `git diff -w -B --ignore-cr-at-eol upstream/master:PATH src/PATH`.
  The fork's blobs can be CRLF while upstream's are LF → plain blob diff is whole-file noise;
  `--ignore-cr-at-eol` (+ `-w`) reveals the true delta (e.g. the fork's
  `pdftextlayoutgenerator.cpp` "136 ins/80 del" was really +60 lines of /ActualText logic +
  2 includes + a header swap).
- Apply ONLY the additive parts by hand (skip cosmetic reformats); modified upstream files keep
  upstream MIT headers (never a GPL header on a modified upstream file); NEW files get
  `Copyright (c) 2026 albdf contributors` + MIT text for the PR.
- **`\r\r\n` double-CR bug (hit 2026-08-08):** building insert text with a Python helper that
  converts `\n`→`\r\n` and ALSO receives already-CRLF content (e.g. `crlf('...' + CRLF)`)
  produces `\r\r\n`. Git's EOL normalization then fails → the ENTIRE file shows as rewritten.
  Detect: `file X` prints "with CRLF, **CR** line terminators", and
  `git diff --ignore-cr-at-eol --stat` shows the real small delta while plain `git diff --stat`
  shows whole-file churn. Fix: byte replace `b'\r\r\n'`→`b'\r\n'`, then normalize the whole
  file: `d.replace(b'\r\n', b'\n').split(b'\n')` → join with `b'\r\n'`.
- Verify before commit: `git diff --ignore-cr-at-eol --stat` must show ONLY intended
  insertions (+N/−0). `git add` stores LF in the blob (upstream `.gitattributes` =
  `* text=auto eol=crlf`), so the GitHub PR diff stays clean.
- Workflow that worked: branch `pr/01-<slug>` → commit code → commit CMake fix (separate) →
  commit test (separate) → build → run → push → `gh pr create --repo JakubMelka/PDF4QT
  --head yolka-wiz:<branch> --base master --draft`.

## 3. Upstream core-only build recipe (this host)

- System Qt 6.8.2 via apt (`/usr/lib/x86_64-linux-gnu/cmake/Qt6` — Core Gui Svg Xml
  LinguistTools Test all present) + vcpkg toolchain for the 9 manifest deps (all in the binary
  cache at `/home/agent/vcpkg-cache/vcpkg`).
- Configure: `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
  -DPDF4QT_BUILD_ONLY_CORE_LIBRARY=ON -DPDF4QT_BUILD_TESTS=ON
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake`
- **CMake bug (fixed + committed as its own commit):** root `CMakeLists.txt:209`
  `qt_add_translations` references GUI targets (`Pdf4QtEditor` … `PdfTool`) unconditionally →
  core-only configure fails with `get_target_property called with non-existent target`.
  Guard with `if(NOT PDF4QT_BUILD_ONLY_CORE_LIBRARY)` — a legit standalone upstream-fix PR.
- Full (non-core-only) build needs Qt6::TextToSpeech, NOT available as `qtspeech6-dev` in
  Debian trixie — core-only avoids that branch entirely (GUI find_package at
  `CMakeLists.txt:68` requires TextToSpeech).
- lupdate generates untracked `PDF4QT_*.ts` artifacts in the repo root during build — delete
  after (never commit; they showed up as the "10 uncommitted changes" warning on `gh pr create`).

## 4. Upstream UnitTests pattern (for PR regression tests)

- One executable per `tst_*.cpp` in `UnitTests/`; mirror an existing entry: `add_executable` +
  `target_link_libraries(... Pdf4QtLibCore Qt6::Core Qt6::Gui Qt6::Test)` + `set_target_properties`
  + `add_test`. Tests are gated independently of `PDF4QT_BUILD_ONLY_CORE_LIBRARY`, so they build
  in core-only mode.
- **`PDF_STREAM_DICT_LENGTH` lives in `pdfconstants.h`** — must `#include "pdfconstants.h"`
  or compile fails (it is NOT in pdfobject.h transitively).
- Fixture: `PDFDocumentBuilder::appendPage(QRectF)` + content stream
  `PDFStream(dict, QByteArray)` — ctor takes RVALUES (`PDFDictionary&&, QByteArray&&`), so pass
  the helper arg by value and `std::move` it. Standard-14 `/BaseFont /Helvetica` resolves to
  bundled Liberation substitutes (`pdffont.cpp` `standardFontSubstituteFileName`) — no font
  file needed in fixtures.
- Drive the layout: `PDFTextLayoutGenerator(PDFRenderer::None, page, &document, &fontCache,
  &cms, &activity, QTransform(), PDFMeshQualitySettings())` → `processContents()` →
  `createTextLayout()`; assert via `getTextBlocks() → getLines() → getCharacters()`
  (QChar per char). BDC/EMC route through the `performMarkedContentBegin/End` virtuals
  (pdfpagecontentprocessor.cpp:3226/3237).
- End file with `QTEST_MAIN(Class)` + `#include "tst_x.moc"`. Run with
  `QT_QPA_PLATFORM=offscreen`.

## 5. PR #1 status + shape (2026-08-08)

- Branch `pr/01-actualtext-preservation`, 3 commits, **+350/−0**: `feat(core)` (PDFTextLayout
  `replaceCharacters`/`getCharacterCount` + layoutgenerator /ActualText span overrides),
  `fix(cmake)` (translations guard), `test(core)` (tst_actualtexttest — 4 cases: length-change
  rebuild, same-length fast path, BDC-without-ActualText no-op, baseline).
- Verified: core builds clean, **6/6 ctest** (5 pre-existing upstream tests + new), no CI on
  PRs (expected — local green is the evidence, quoted in the PR body).
- Opened as **draft PR #414** (`yolka-wiz:pr/01-actualtext-preservation` → master).

## 6. Dep verdict — KEEP harfbuzz+fribidi (3 parallel subagents, 2026-08-08)

Empirical (Qt 6.8.2 probes, `/tmp/rtlprobe/`): ~70% of the FriBidi/HarfBuzz surface ports 1:1
to public Qt APIs (bidi runs via QTextLayout+glyphRuns, GIDs/advances/positions, ink bbox).
Three blockers for a full Qt-native port:
1. **Glyph→cluster mapping** (`hb_buffer` cluster values → ToUnicode + /ActualText + lam-alef /
   decomposed-yeh handling): `QGlyphRun::stringIndexes()` is EMPTY when filled from
   QTextLayout (verified); no other public cluster API; MONOTONE_CHARACTERS mark clusters
   irreproducible. Most behavior-pinned part of the engine.
2. **String-level bidi reorder** (`invertToVisual/Logical` via `fribidi_reorder_line`):
   Qt 6 has NO public string-reorder API (algorithm lives in private QTextEngine) — a port
   means a hand-written UAX#9 (~300-500 lines) for zero user-visible gain.
3. **Ts mark-offset recalibration**: `QGlyphRun::positions()` exposes GPOS y-offsets but with
   different sign/magnitude than HB `y_offset` — full calibration cycle against pixel-band tests.

Qt-native notes that ARE public and verified: shaping via QTextLayout gives the same GIDs as HB
(سلام → 35,69,11,72); `QRawFont::advancesForGlyphIndexes` has hmtx parity (gid 77 → 455.7u vs
HB 456u); `QRawFont::boundingRect(gid)` gives ink bbox (fatha gid 380 → (0,-11,3x3));
`QTextLine::glyphRuns()` come back in visual run order with per-run `isRightToLeft()` but glyphs
inside an RTL run are logical-order/descending-x (needs per-run reversal for PDF emission).

Upstream-integration corroboration: upstream text pipeline is FreeType-glyph-level (no shaping);
`harfbuzz`+`fribidi` = canonical FreeType companions (MIT / LGPL-2.1 linked — MIT-compatible);
risk is SOCIAL (stable minimal vcpkg.json, "Qt already bundles HarfBuzz" counter). Rebuttal for
the PR design note: QTextLayout hides the buffer-level data a PDF writer needs (clusters,
bidi levels, GPOS offsets), and would be a second parallel text stack.
