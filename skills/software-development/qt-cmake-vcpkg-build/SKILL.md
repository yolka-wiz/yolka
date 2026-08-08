---
name: qt-cmake-vcpkg-build
description: "Build/test Qt C++ projects via CMake + vcpkg manifest mode."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vcpkg, cmake, qt, cpp, build, ctest, headless, offscreen]
    related_skills: [package-mirror-config, dev-toolchain-provisioning, docker-essentials, git-essentials]
---

# Qt / CMake / vcpkg Build & Test

Build and verify a C++/Qt project that uses **vcpkg in manifest mode**
(`vcpkg.json` in the tree; a `cmake` configure auto-installs deps from
source). Use when the user says "install the required packages and test on
the pdf/file", after an ephemeral dev container restart (toolchain wiped),
or before trusting a CI-style claim on a fresh machine.

## When to Use

- "install the required packages and build/test the project"
- Rebuilding after a container restart where the OS layer (Qt, tools) was wiped
- Verifying a fork builds headless before/after a rename or doc change

## Workflow (fresh Linux container)

```bash
# 1. System prereqs — note: vcpkg bootstrap needs ZIP specifically.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential cmake ninja-build pkg-config git ca-certificates curl unzip zip \
  g++ clang clang-format \
  qt6-base-dev qt6-svg-dev qt6-tools-dev qt6-translations-l10n \
  libfontconfig1-dev fonts-liberation ccache

# 2. vcpkg (shallow clone + bootstrap). MUST run AFTER apt finished —
#    bootstrap checks for curl/unzip/zip and fails with "Could not find zip".
git clone --depth 1 https://github.com/microsoft/vcpkg.git /path/to/vcpkg
cd /path/to/vcpkg && bash bootstrap-vcpkg.sh -disableMetrics

# 3. Configure — manifest mode: FIRST configure builds every dep from source
#    (openssl, blend2d, harfbuzz, fribidi, ...) — can take 5-10 min. Run it in
#    the background; keep the vcpkg tree so later configures are cached.
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DVCPKG_OVERLAY_PORTS=/path/to/repo/src/vcpkg/overlays \
  -D<PROJECT>_BUILD_TESTS=ON

# 4. Build + test — Qt CLI aborts without a display UNLESS offscreen is set.
cmake --build build
QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure

# 5. Repo smoke suite (if present) + CLI spot checks, offscreen everywhere.
QT_QPA_PLATFORM=offscreen bash src/tests/smoke.sh src/build/bin/<binary> src/tests/fixtures
```

## Pitfalls (all hit in the field)

1. **vcpkg bootstrap needs `zip` — not just `unzip`.** The bootstrap error
   says "Could not find zip" even when curl/unzip/tar exist. Add `zip` to the
   apt list from the start; re-running bootstrap after installing it works.
2. **Never run vcpkg bootstrap in parallel with the apt install that provides
   its prereqs.** It fails silently mid-script ("missing curl" style messages
   that look like a real blocker); sequence them: apt first, then bootstrap.
3. **`QT_QPA_PLATFORM=offscreen` is mandatory** for every headless Qt
   invocation — the binary aborts with a "could not connect to display" xcb
   error otherwise. Export it per-command or in the session; do not expect
   `--version` to survive without it.
4. **First configure is the long pole.** Manifest deps compile from source
   (OpenSSL, blend2d/asmjit, HarfBuzz, FriBidi, FreeType...). Background it
   with `notify_on_complete`, don't poll-loop; then check the log tail for
   `Configuring done`/`Build files have been written`.
5. **blend2d/asmjit often need an overlay**: if the repo has
   `src/vcpkg/overlays`, pass `-DVCPKG_OVERLAY_PORTS` or the build fails on
   CMake recursion/version pins. Check for the overlay dir before configuring.
6. **Render/CLI flag names differ from README guesses.** When a CLI rejects
   an option (`Unknown option 'image-output'`), run `<binary> <cmd> --help`
   and use the REAL flag (e.g. `--image-output-dir`, not `--image-output`).
7. **Verify the rename/version on the built binary**: `--version` should print
   the current project name/version (`albdf 0.1.0`); a stale app-name string
   means the rename missed `setApplicationName`.
   **Version-bump trap (hit 2026-08-07): after bumping the project version
   (e.g. `set(ALBDF_VERSION 0.1.0)` → `0.2.0`), the FIRST `ctest` failure is
   usually a test/script that HARDCODES the old version string** — albdf's
   `src/tests/smoke.sh` grepped `albdf (0\.1\.0|1\.6\.0\.0)` and failed with
   `FAIL version string (got: albdf 0.2.0)`. Before bumping, grep for the old
   version across tests/scripts (`grep -rn "0\.1\.0" src/tests/ scripts/`), and
   when fixing, make the check FUTURE-PROOF so the next bump doesn't break it
   again: `grep -qE "albdf (0\.[0-9]+\.[0-9]+|1\.6\.0\.0)"`. Always run the full
   gate after a version bump — the binary version string is exercised by
   smoke/CLI tests that Release ctest alone may not surface until you look.
8. **System Qt vs vcpkg Qt**: manifest deps come from vcpkg; system Qt (apt)
   is only for tooling/UI deps. Don't add Qt to vcpkg.json unless upstream
   requires it.
9. **Build dir = where CMakeLists.txt is, NOT the repo root.** For albdf the
   CMakeLists.txt lives in `src/`, so `cmake -S . -B build` runs from `src/`
   and the build dir is **`src/build`** (repo root has no CMakeLists; the
   root AGENTS.md's bare `cmake -S . -B build` is misleading). ctest:
   `QT_QPA_PLATFORM=offscreen ctest --test-dir src/build`. `ci/run-ci.sh`
   handles this by `cd`ing into `src/` first — mirror that.
10. **QFlags is 32-bit-only before Qt 6.9 — flag enums with values ≥
    0x100000000 don't compile.** Any `Q_DECLARE_FLAGS`/`Q_DECLARE_OPERATORS_FOR_FLAGS`
    enum containing an enumerator ≥ 2^32 gets a 64-bit underlying type, and
    Qt < 6.9 dies with: `qflags.h: static assertion failed: QFlags uses an
    int as storage, so an enum with underlying long long will overflow`
    (note `(8 <= 4)`). Qt only added 64-bit QFlags in 6.9. This bites when
    the project docs declare Qt ≥ 6.9 (e.g. "Qt 6.10") but the machine/CI
    has Qt 6.8 (Debian 13 apt = 6.8.2; a workflow pinning `6.8.*` also
    fails) — the author's env builds, yours doesn't. Diagnose:
    `grep -nE '= 0x[0-9A-Fa-f]{9}' <header>` for the oversized enumerator,
    `git log -S 'MovePage = 0x100000000' --oneline -- <file>` for the
    introducing commit, `git show <base>:<file>` to diff against the
    vendored baseline. Fix options: (a) renumber the >32-bit flags into the
    32-bit range — but that's an API change, check AGENTS.md / ask the
    orchestrator first; (b) build with Qt ≥ 6.9, e.g.
    `pip install --user --break-system-packages aqtinstall &&
    aqt install-qt linux desktop 6.10.x linux_gcc_64 -O ~/qt` then pass
    `-DCMAKE_PREFIX_PATH=~/qt/6.10.x/gcc_64`; (c) **replace
    `Q_DECLARE_FLAGS` + `Q_DECLARE_OPERATORS_FOR_FLAGS` with a small 64-bit
    flags class** — member `testFlag`, member `operator|(&,|,|=)` on
    `Enum`, plus ONE free `operator|(Enum, Enum)` and one free
    `operator|(Enum, Flags)`, storing `quint64 m_bits`; enum layout stays
    untouched (fork-friendliest). Verified 2026-08-06 on albdf (Qt 6.8.2,
    GCC 14): fresh build + ctest 12/12 green.
    **ADL shadowing trap (the fix's own pitfall):** the free
    `operator|(Enum, Enum)` MUST be declared at **global scope**, NOT inside
    the project's namespace. Unqualified lookup from inside
    `namespace pdftool` stops at the first scope that declares `operator|`;
    a pdftool-scope operator| SHADOWS the QFlags operator| declarations Qt
    puts at global scope, so unrelated code in that namespace falls back to
    built-in `int|int` and breaks with `invalid conversion from 'int' to
    'Enum'` (hit in pdftooldeletepage.cpp: `PDFOptimizer::RemoveUnusedObjects
    | ShrinkObjectStorage`). Reproduce/verify with a two-case minimal test:
    same expression at global scope compiles, inside the namespace fails.
    **Stale-build trap:** a checkout whose build dir predates the breaking
    commit still "compiles" until something forces a rebuild — "baseline was
    green" (ctest 11/11!) can be true against a stale `build/bin/albdf`
    while HEAD is uncompilable. Before trusting a baseline, compare
    `stat -c %y build/bin/<binary>` against `git log -1 --format=%ci HEAD`
    — binary older than the suspect commit = stale, must rebuild first.
    Never dispatch agents or report "baseline green" on a binary older than
    the code you're about to test.

11. **albdf on this host: vcpkg is at `/home/agent/vcpkg-cache/vcpkg`, NOT
    `/workspace/vcpkg`** (src/AGENT.md's path is stale here; the orchestrator
    corrected it). `vcpkg.json` lists no Qt — system Qt 6.8.2 (apt
    qt6-base-dev) is used. Configure:
    `export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg && cmake -S . -B build
    -G Ninja -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake
    -DALBDF_BUILD_TESTS=ON`. Also: pre-commit hooks are NOT installed in
    git worktrees — don't expect REPO_MAP.md regeneration on commit.

12. **QProcess CLI-test helpers: never return a PATH into a function-local
    QTemporaryDir.** A helper that runs the CLI into a local QTemporaryDir
    and returns the artifact's FILE PATH fails silently at the call site:
    the temp dir (and its files) is destroyed when the helper returns, so
    `QImage(path)` loads 0×0. First `tst_redacttest.cpp` run failed exactly
    like this (`QSize(0x0)`) — a genuine RED-phase catch, not a production
    bug. Load/copy the artifact INSIDE the helper before the temp dir dies
    (return the `QImage`/bytes, not the path), or keep the QTemporaryDir
    alive at the caller.
    **Wiring a new CLI integration test** (albdf `src/UnitTests/CMakeLists.txt`,
    one `add_executable` per `tst_*.cpp`, explicit enumeration, no globbing):
    `target_link_libraries(... Pdf4QtLibCore Qt6::Core Qt6::Gui Qt6::Test)`,
    fixture paths via `target_compile_definitions`,
    `set_target_properties` with `RUNTIME_OUTPUT_DIRECTORY`,
    `add_test(NAME UnitTestsX COMMAND ...)` +
    `set_tests_properties(... ENVIRONMENT "QT_QPA_PLATFORM=offscreen")` +
    `add_dependencies(UnitTestsX albdf)`. Mirror the last-registered
    integration target (UnitTestsPageOps / UnitTestsRedact). The suite
    binary is found via `QCoreApplication::applicationDirPath() + "/albdf"`
    (requires `QTEST_GUILESS_MAIN`) and must end with
    `#include "tst_x.moc"`.

13. **albdf local CI gate (`ci/run-ci.sh`)** — 4 stages: (1) Release
    configure+build into `src/build`, (2) offscreen Release ctest (14/14
    incl UnitTestsRedact + UnitTestsRender after M10), (3) fresh `build-asan` Debug ASAN/UBSAN build +
    ctest (15-40 min fresh — ALWAYS background with notify_on_complete;
    foreground exceeds timeout), (4) clang-format gate on authored files
    only (`git diff 6bf5047..HEAD -- '*.cpp' '*.h'` minus 5 excluded
    vendored/upstream files — cherry-pick hygiene). Stage logs:
    /tmp/ci-build.log, /tmp/ci-ctest.log, /tmp/ci-asan-cfg.log,
    /tmp/ci-asan-build.log, /tmp/ci-asan-ctest.log.
    **Exit-code trap:** `bash ci/run-ci.sh 2>&1 | tee log` reports TEE's
    exit code — 0 even when the gate FAILS (no pipefail). Read the
    script's final `CI: ALL GREEN`/`CI: FAILED` line, or run
    `bash -c 'set -o pipefail; bash ci/run-ci.sh | tee log; echo "real=$?"'`.
    A format-gate failure is branch-blocking (AGENTS.md §6) and needs a
    NEW commit, not a working-tree edit. Diagnose with
    `clang-format --dry-run --Werror <file>` (names the violation), then
    `clang-format <file> | diff <file> -` (exact reflow); typical
    violations: include reordering + case-brace collapse (`case 1:` newline
    `{` → `case 1: {`).
    **Modifying an upstream-derived file pulls it INTO the format gate —
    expect it to fail, and exclude it by policy.** The authored-file list is
    `git diff <fork-base>..HEAD -- '*.cpp' '*.h'` minus explicit exclusions.
    The moment you modify a vendored upstream file (a bug fix, a determinism
    change), it enters that diff and gets format-checked — and pristine
    upstream formatting almost always differs from the repo's `.clang-format`
    (include order, `case 1:` brace style). Verify BEFORE assuming your edit
    is the problem: `git show <fork-base>:<file> > /tmp/pristine.cpp &&
    clang-format --dry-run --Werror /tmp/pristine.cpp` — if the PRISTINE
    file already fails, the fix is to ADD it to the `grep -vE` exclusion
    list in `ci/run-ci.sh` (matches the documented policy: upstream-derived
    modified files are exempt so cherry-pick diffs survive; your added lines
    must still match surrounding style). Propagate the exclusion to every
 parallel branch that modified the same file, or each branch's gate fails
 on the same file. (Hit 2026-08-06: determinism fix touched
 pdfdocumentbuilder.cpp; three branches each needed the exclusion.)
 **Vendoring WHOLE upstream dirs needs DIRECTORY-level exclusions, not
 per-file.** The moment you `git archive <upstream-tag> <dir> | tar -x` a
 multi-directory GUI/app tree into the fork (M12: Pdf4QtLibGui,
 Pdf4QtLibWidgets, Pdf4QtEditor, Pdf4QtViewer, Pdf4QtPageMaster — 358
 files), the format gate flags EVERY upstream-formatted .cpp/.h in the
 diff. Add one `grep -vE '^src/Pdf4QtLibGui/'` per dir (trailing slash,
 before the closing `)"`), NOT 358 per-file lines. Keep the vendored
 dirs' own authored edits out of the authored list too — the policy is
 cherry-pick hygiene. CI will catch the omission on the PR (format job is
 the fast canary: `clang-format gate FAILED` while build/asan pass).
 **Patch-tool backslash trap when editing the grep -vE exclusion list:**
 the `patch` tool DOUBLE-escapes `\.` in a `grep -vE '\.cpp$'` line to
 `\\.` (hit twice, 2026-08-06 and 2026-08-07). The line still looks
 right in the diff but the regex now matches a literal backslash and the
 exclusion silently stops working — or configure breaks. Verify after ANY
 patch to run-ci.sh: `sed -n '...p' ci/run-ci.sh | cat -A` must show ONE
 backslash before the dot, and the un-excluded file must still be flagged
 by `bash ci/run-ci.sh --only-format`. Fix doubles with a Python byte
 replace (`content.replace(r"\\.cpp", r"\.cpp")`), not another patch.
 **Branch-mixup trap when a subagent committed your fix:** a format-gate
 fix made while a child's branch is checked out lands on the CHILD's
 branch; the PR's branch stays red. Check `git branch --show-current`
 before committing, then `git cherry-pick <sha>` onto the PR branch and
 push. (Hit 2026-08-07: format exclusion committed to m12/gui-ci; PR #7
 on m12/gui-restore needed the cherry-pick.)
    See
    references/ci-gate-run-2026-08-06.md` for the full stage layout and
    a real run transcript.

14. **Determinism tests flake ONLY under ASAN — suspect wall-clock timestamps,
    not your new code.** A byte-determinism test that runs the CLI twice and
    compares output hashes (`QCOMPARE(sha256OfFile(a), sha256OfFile(b))`) can
    pass in Release and fail under ASAN/UBSAN with a hash mismatch, no
    sanitizer report at all. Root cause: sanitizer builds run SLOWER, so the
    two runs straddle a wall-clock second boundary, and any output that
    stamps `QDateTime::currentDateTime()` (PDF `CreationDate`/`ModDate`,
    tarball mtimes, generated headers) differs between the runs. Real case
    (albdf 2026-08-06): Release 12/12 green; ASAN ctest failed only
    `PageOpsTest::movePageMovesContent` (different sha256). Also explains an
    intermittent "1 transient failure in 7 runs" in Release.
    **Diagnose:** confirm the flaky test compares two *runs* of the same op;
    diff the two outputs (`cmp -l a b | head`) — if the first diff is in an
    Info/timestamp dict, it's the wall clock. **Fix (project-dependent,
    orchestrator sign-off for core libs):** deterministic timestamps —
    `SOURCE_DATE_EPOCH` if set (reproducible-builds convention), else a FIXED
    epoch, never wall-clock. In albdf: replace the single
    `PDFObjectFactory::operator<<(WrapCurrentDateTime)` implementation; that
    one change covers all ~13 date sites (trailer Info, signatures,
    annotations). After fixing, verify determinism across a sleep:
    run op, `sleep 3`, run op again → identical sha256. Then re-run ASAN
    ctest twice to prove the flake is gone, not lucky.
    **Propagate the fix to every parallel branch that runs the gate** — the
    flake will hit each one (same core file); cherry-pick/copy it into all
    worktrees and re-verify each.

15. **GitHub Actions toolchain: two silent killers — vcpkg without bootstrap,
    and aqt's flaky Qt install.** When hosting the vcpkg+Qt build on
    GitHub-hosted runners (composite `setup-toolchain` action), two failures
    hit with the SAME signature (every job dies in the setup step, ~2s in,
    no build ever starts) but DIFFERENT root causes:
    - **vcpkg clone ≠ usable vcpkg.** `git clone` of microsoft/vcpkg gives
      the SOURCE TREE only — the `vcpkg` executable is produced by
      `bootstrap-vcpkg.sh`. A composite action that clones then runs
      `"${VCPKG_ROOT}/vcpkg" version` fails with
      `/path/vcpkg/vcpkg: No such file or directory` and exit 127. Fix:
      run `"${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics` after clone.
      (Locally this never bites because the pre-existing vcpkg cache tree
      was bootstrapped long ago — CI's fresh clone is different.)
    - **aqt Qt install intermittently fails on GH runners with `The packages
      ['qt_base'] were not found while parsing XML of package information!`**
      (miurahr/aqtinstall#769, jurplel/install-qt-action#231). aqt resolves
      the base Qt package through an Updates.xml fetch whose content depends
      on which Qt mirror/CDN edge the runner reaches; the same aqt 3.3.0 +
      same command works locally (via mirror.maeen.sa) and fails on GH.
      Diagnose by exact error text, NOT by re-running locally (local success
      proves nothing). Robust fix: REPLACE `jurplel/install-qt-action` with
      a direct shell step — `python3 -m pip install "aqtinstall==3.3.*"`,
      then a 3-attempt retry loop calling
      `python3 -m aqt install-qt linux desktop <VER> linux_gcc_64
      --archives qtbase qtsvg --outputdir <dir> --timeout 30` (retry lets
      aqt rotate mirrors between attempts), then locate qmake
      (`find <dir> -path '*/bin/qmake'`) and export the contract vars
      (`QT_ROOT_DIR`, `CMAKE_PREFIX_PATH`). Also pin the EXACT Qt version
      (`6.8.3`, not `6.8.*`) — wildcard resolution is part of the flaky XML
      path — and install the Qt runtime xcb deps (libxcb-icccm4, libxcb-*,
      libxkbcommon-x11-0, libgl1-mesa-dev) the old action's install-deps
      provided. (Hit 2026-08-07: five consecutive GH CI runs failed at
      setup-toolchain; each fixed one layer — bootstrap, then module XML,
      then wildcard, then archives+retry — the retry loop was the one that
      got jobs actually building.)
    - **Qt 6.8.3 prebuilt binaries are built against ICU 73 — ubuntu-24.04
      ships ICU 74 (ABI-incompatible).** Once the toolchain setup succeeds and
      jobs actually build, the NEXT failure is `rcc: error while loading
      shared libraries: libicui18n.so.73: cannot open shared object file`
      (also libicuuc.so.73, libicudata.so.73). The Qt online binaries are
      built on RHEL against ICU 73; NO distro packages ICU 73 (Ubuntu
      archives have 71/72/74 only; Debian stable jumped 72→74/76).
      **Do NOT symlink ICU 74 → 73** — ICU major version IS the ABI boundary;
      Qt fails with `undefined symbol: ucnv_reset_73`. Fix (verified
      2026-08-07, ~1 min): build ICU 73 from the ICU upstream release tarball
      in the toolchain action and export `LD_LIBRARY_PATH`:
      `curl -sL https://github.com/unicode-org/icu/releases/download/release-73-2/icu4c-73_2-src.tgz -o /tmp/icu73.tgz &&
      tar xzf /tmp/icu73.tgz -C /tmp && cd /tmp/icu/source &&
      ./configure --prefix=/tmp/icu-build --disable-tests --disable-samples --disable-dyload &&
      make -j$(nproc) && make install` then
      `echo "LD_LIBRARY_PATH=/tmp/icu-build/lib:...\${LD_LIBRARY_PATH:-}" >> GITHUB_ENV`.
      Verify locally first: `LD_LIBRARY_PATH=/tmp/icu-build/lib <qt>/libexec/rcc --version`
      must print the Qt version. NOTE the local dev container avoids all this
      because it uses SYSTEM Qt (apt qt6-base-dev), which is built against the
      distro's current ICU — the aqt prebuilt is the only path that hits it.
      **CRITICAL ORDERING: build ICU BEFORE the aqt Qt install.** aqt's
      post-install step EXECUTES qmake to verify the install ("Patching
      .../bin/qmake"), and that qmake needs ICU 73 on LD_LIBRARY_PATH. Putting
      the ICU step after the Qt install fails with the same
      `libicui18n.so.73: cannot open shared object file` — the qmake check
      runs inside the Qt step, before your later step ever executes. GITHUB_ENV
      lines are applied to SUBSEQUENT steps, so the ICU step must come first:
      build ICU → write `LD_LIBRARY_PATH=/tmp/icu-build/lib:...` to GITHUB_ENV
      → then install Qt (the env is already active for it) → append the Qt lib
      dir to LD_LIBRARY_PATH for the build steps. Verified locally: aqt install
      with ICU 73 already on LD_LIBRARY_PATH completes and patches qmake OK;
      without it, qmake dies. (Hit 2026-08-07: run 7 put ICU after Qt and
      still failed; run 8 moved ICU first and reached the real project build.)
    - **After the toolchain is green, the FIRST real project-compile failure is
      usually missing system headers.** Once setup passes and jobs actually
      build, expect a `fatal error: <header>: No such file or directory` from
      the project's own sources — e.g. albdf's `pdffont.cpp` includes
      `<fontconfig/fontconfig.h>`, which ubuntu-24.04 does not have by
      default. Fix: add the dev packages to the toolchain apt step
      (`libfontconfig1-dev libfreetype-dev` for fontconfig/freetype users).
      Check what system headers the project includes before writing the apt
      list (`grep -rn '#include <' src/ | grep -v Qt | sort -u`), and mirror
      the packages the local machine has (`dpkg -l | grep libfontconfig`).
      **CI failure triage order for "everything fails in setup":** (1) exact
    failing line from `gh run view <id> --log-failed`; (2) if exit 127 +
    `No such file or directory` → missing bootstrap/executable step; (3) if
    an aqt/XML parse error → mirror flakiness, fix with retry not by
    re-running locally; (4) if `rcc`/Qt tool fails on a shared library →
    Qt-built-against-ICU mismatch, build the exact ICU from source; (5)
    `clang-format gate` succeeding while build jobs fail means the failure is
    in the toolchain setup, not the code — the format job skips Qt/vcpkg
    entirely (install-qt: false), so it is the control that isolates setup
    from build. Full case study in
    references/gh-actions-toolchain-ci-2026-08-07.md.

16. **Shell benchmarks/scripts that parse NUMBERS from tool output break on
    locale thousands separators — and the failure looks like an assertion
    bug, not a perf problem.** A benchmark that generates a 1000-page fixture
    and asserts `PAGES = "1000"` by `awk '/Page count/ {print $3}'` fails
    with every op `ok=0` when the tool prints `Page count         1,000`
    (comma from locale-formatted output; small docs like the 5-page
    multipage fixture print `5` with no comma, so the script passes locally
    on small fixtures and fails only on the big one). Symptom on GH CI:
    `op=info,ms=29,ok=0,pages=1,000`, `result=FAIL,ops=5,failed=5` while all
    ms are far under the threshold — the tell is `max_ms` tiny + `failed=N`
    high. Fix the PARSE, not the threshold:
    `awk '/Page count/ {gsub(/,/, "", $3); print $3; exit}'` — and the same
    for any other numeric assertion (search match counts etc.). After fixing,
    re-run the benchmark locally on the BIG fixture before pushing
    (`bash scripts/benchmark.sh --work-dir /tmp/bench-fixed` → `result=PASS,
    ops=5, failed=0`).
    **Headless default belongs INSIDE the timing helper, not only at the CI
    job level.** The same script's `time_op()` ran the binary via
    `OP_OUT="$("$@" 2>&1)"` — with no display the binary aborts exit 134
    (SIGABRT, "Aborted") and every op reports `ASSERTION FAILED` even
    though CI sets `QT_QPA_PLATFORM=offscreen` at the job level. Make the
    script self-contained:
    `OP_OUT="$(QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$@" 2>&1)"`.
    This also catches the case where a local run forgets to export the var.
    (Hit 2026-08-07: albdf `scripts/benchmark.sh` — GH CI showed 5/5 ops
    asserted-fail at 30–90ms; local repro first blamed exit 134, then the
    comma parse. Both fixes landed in one commit, benchmark PASS 5/5.)

17. **"Does this foreign/vendored Qt code compile on MY Qt version?" — answer
    it with a header token sweep, not README claims or curated grep lists.**
    Upstream may declare "Qt 6.9 or higher" in its README while your
    machine/CI has Qt 6.8 (Debian apt = 6.8.2) — and the code can still be
    fully 6.8-compatible. Don't hand-grep a candidate list from memory: you
    miss APIs AND cry wolf over ones that already exist. Definitive, no-build
    audit: (a) regex-extract every `Q<Class>::<method>` token from the target
    sources (`.cpp/.h`; skip project classes and `tr()`); (b) build a set of
    ALL identifiers found in the installed Qt headers (`find
    /usr/include/<triplet>/qt6 -name '*.h'`); (c) any method missing from the
    index is a REAL candidate — everything else is proven present. Verified
    run (albdf vendored GUI, 2026-08-07, Qt 6.8.2): 400 unique tokens → only
    3 missing, all `QTextToSpeech`/`QVoice` (a not-installed MODULE, not a
    6.9 version bump — the module exists in Qt 6.8 too); everything else,
    incl. `QColor::fromString` (Qt 6.8+), `QImage::convertToColorSpace`
    (6.4+), `setColorSpace`, `QKeySequence::fromString`, compiles on 6.8.2.
    Known Qt 6.9-only QColorSpace members to check by name when QColorSpace
    appears: `primaryPoints()`, `TransferFunction::PerceptualQuantizer`,
    `::HybridLogGamma`, `Primaries::CinemaGamut` (all absent from 6.8.2
    headers). Caveats: (i) the sweep covers METHOD names only — enum VALUES
    added in newer Qt (new `QKeySequence::StandardKey`, `Qt::*` flags, etc.)
    need a separate spot-check of the values actually used; (ii) inherited
    methods resolve fine because the index is module-wide, not per-class.
    Full script + results in `references/qt-version-api-audit-2026-08-07.md`.
    **`QT_<MODULE>_LIB` is the compile-out guard macro:** Qt6 CMake defines
    `QT_<MODULE>_LIB` (e.g. `QT_TEXTTOSPEECH_LIB`) as a compile definition
    ONLY while the matching `Qt6::<Module>` target is linked. Drop the module
    from `target_link_libraries` and the macro vanishes — `#if defined(...)`
    blocks go dead automatically and restore automatically if the module
    ever returns. Verify guards are balanced per file with
    `grep -c '#if defined(QT_TEXTTOSPEECH_LIB)' <file>` and that no UNGUARDED
    `#include <Q<Module>>` remains (a module header not on disk is a hard
    compile error).
    **Compiling out an unprovisioned Qt module in VENDORED code: keep the
    class API, stub the implementation.** When the module isn't installed
    (no dev package, no CMake target) and the code is upstream-vendored
    (cherry-pick hygiene), do NOT delete the class or its uses — the rest of
    the tree references it by type (constructors, pointer members,
    UI wiring). Instead: (a) guard every `#include <Q<Module>>` and each
    direct module-API call site with `#if defined(QT_<MODULE>_LIB)` (the
    macro is defined only when the target is linked — drop the module from
    the CMake link and the guards go dead); (b) rewrite the module's own
    TU(s) as a no-op stub that preserves the exact class/method surface —
    `isValid()` returns false (the UI that gates on it hides itself), other
    methods are inert; (c) keep the header's pointer member as a
    forward-declared pointer (compiles without the module). Mark the stub
    with a clear "fork divergence — restore from upstream tag <tag> if the
    module is ever provisioned" comment. (Hit 2026-08-07: Qt6TextToSpeech
    absent on the build box; PDFTextToSpeech stubbed — sidebar Speech page
    auto-hides because `getValidPages()` filters on `!isValid()` — and the
    settings dialog's `availableEngines()` returns empty under the guard.
    Three files touched; CMake link line dropped the module.)
    **Linux CMake facts (empirically verified 2026-08-07 in a /tmp scratch
    project — do not re-test): `.rc` files listed unconditionally in
    `add_executable` are silently IGNORED on Linux** — configure AND build
    succeed (CMake emits no rule when no RC compiler exists). icon.rc is NOT
    a Linux blocker; leave it in place to keep upstream CMake pristine.
    `WIN32_EXECUTABLE ON` / `MACOSX_BUNDLE ON` target properties are no-ops
    on Linux.
    **`#elif` grep trap:** a regex like `else` does NOT match `#elif`. Before
    reporting an "always-compiled `static_assert(false)` in the #else branch"
    Linux blocker, read the FULL conditional chain — upstream's
    `#ifdef Q_OS_WIN ... #elif defined(Q_OS_UNIX) // TODO ... #else
    static_assert(false) ... #endif` compiles fine on Linux because
    Q_OS_UNIX is defined and the static_assert is dead code. Grep
    `#if|#ifdef|#elif|#else|#endif` explicitly and view the block before
    flagging anything.

18. **Qt AppImage packaging in a container/CI: three silent blockers between
    "linuxdeploy found" and a working AppImage.** Building a Qt GUI AppImage
    with linuxdeploy + linuxdeploy-plugin-qt + appimagetool (the tools
    themselves are AppImages) hits three environment traps in sequence — all
    fixed with a one-liner, none visible until the exact step fails:
    - **AppImage tools self-mount via FUSE; containers often lack fusermount
      or /dev/fuse.** Symptom: `Error: No suitable fusermount binary found
      on the $PATH / $FUSERMOUNT_PROG not set / Cannot mount AppImage` —
      even when `/dev/fuse` exists, the `fusermount` BINARY is missing.
      Fix (in the packaging script, not just the shell):
      `export APPIMAGE_EXTRACT_AND_RUN=1` — makes every AppImage tool
      self-extract to a temp dir and run instead of FUSE-mounting. It is
      also faster in CI.
    - **The qt plugin fails on a MISSING icon engine:**
      `ERROR: Cannot deploy non-existing library file:
      .../qt6/plugins/iconengines/libqsvgicon.so` (exit 1 from the qt
      plugin, after it deployed everything else). Debian splits Qt's SVG
      icon engine into its own package: `qt6-svg-dev` installs the LIBRARY
      + CMake configs but NOT the runtime plugin. Fix:
      `apt-get install -y qt6-svg-plugins` (provides
      `/usr/lib/x86_64-linux-gnu/qt6/plugins/iconengines/libqsvgicon.so`).
      The GUI uses SVG icons from its .qrc resources, so this plugin is
      REQUIRED — not optional.
    - **appimagetool needs the `file` command:**
      `file command is missing but required, please install it` (exit 1
      from the appimage output plugin, AFTER linuxdeploy succeeded). Fix:
      `apt-get install -y file` — a bare container often lacks it.
    Order the fixes: APPIMAGE_EXTRACT_AND_RUN in the script (permanent),
    then apt `qt6-svg-plugins` + `file`. The linuxdeploy qt-plugin output is
    verbose (`[qt/stdout] Deploying ...` for every dep); the failing step is
    the LAST `ERROR:` line — grep for `ERROR` not `Deploying`. A packaging
    script should also `cp -a` the project's own libs
    (`lib/libPdf4Qt*.so*`) into `AppDir/usr/lib` and let linuxdeploy resolve
    SYSTEM libs (Qt, harfbuzz, freetype) automatically — do NOT copy vcpkg
    `installed/.../lib/*.so*` wholesale (the GUI links system harfbuzz/
    freetype, not vcpkg's — verify with `ldd` first). (Hit 2026-08-07:
    albdf 0.3.0 AppImage — three sequential failures, each fixed by one of
    the above; packaging script at `packaging/build-appimage.sh`.)
    **VERIFY the AppImage actually runs — linuxdeploy success ≠ working
    bundle.** The qt plugin only bundles the platform plugin(s) the app
    pulled in — an offscreen-tested GUI ships `libqxcb.so` ONLY, no
    `libqoffscreen.so`. So (a) launch under a virtual display, not offscreen:
    `APPIMAGE_EXTRACT_AND_RUN=1 timeout 8 xvfb-run -a ./app.AppImage file.pdf`
    and confirm it STAYS ALIVE (`xvfb-run -a bash -c '... & PID=$!; sleep 6;
    kill -0 $PID && echo STILL RUNNING; kill $PID'` — rc 143 after your kill
    is SUCCESS; rc 124 from `timeout` also means it survived); (b) check the
    bundled plugins after `--appimage-extract`:
    `ls squashfs-root/usr/plugins/platforms/` must contain `libqxcb.so`.
    **Leaked-env trap:** a shell that earlier exported
    `QT_QPA_PLATFORM=offscreen` makes the xcb-only AppImage FAIL with
    `Could not find the Qt platform plugin "offscreen"` even though the
    bundle is fine — `unset QT_QPA_PLATFORM` (or `env -u`) before the xvfb
    launch, or you'll chase a phantom packaging bug. Also verify the upload:
    re-download the release asset and `sha256sum` both sides — byte-identical
    upload is the real proof (0.3.0: `7f6e4204...` AppImage and
    `5128bf82...` tarball matched).

## Verification Checklist

- `ctest` — all targets pass (offscreen)
- smoke suite (if present) — all checks pass
- `--version` prints current name/version
- CLI round-trip on a fixture: `info`, `fetch-text`, and a project-specific
  op (add-text/search/delete) all exit 0
- **Verify generated artifacts with an INDEPENDENT tool, not just the
  project's own renderer.** A project's own renderer + its own golden images
  can be *self-consistently wrong*: albdf's golden tests passed while ALL
  RTL output mapped to wrong glyphs (Latin 'A's), because goldens were
  committed from the same buggy pipeline and text extraction uses
  ToUnicode/ActualText (glyph-independent). For PDF output, render with
  Ghostscript (`gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r72`) and compare
  ink bboxes/shapes to expectations; for anything else, use a second
  independent consumer. Golden images passing ≠ output correct.

## Reference

- `references/albdf-build-2026-08-05.md` — concrete session: package list,
  vcpkg bootstrap failure + fix, configure output, 11/11 ctest, 34/34 smoke,
  RTL CLI round-trip.
- `references/albdf-qflags-64bit-break-2026-08-06.md` — QFlags 32-bit
  overflow case study: symptom, `git log -S` diagnosis trail, Qt 6.8-vs-6.10
  pin mismatch, and the renumber-vs-newer-Qt fix routes.
- `references/qt-qflags-64bit-class-fix-2026-08-06.md` — the verified
  drop-in 64-bit Options class (code shape), the ADL shadowing trap
  (namespace-scope `operator|` breaks unrelated QFlags code — put free
  operators at global scope), and the stale-baseline stat-vs-gitlog check.
- `references/ci-gate-run-2026-08-06.md` — local CI gate (`ci/run-ci.sh`)
  stage layout, log paths, the tee/pipefail exit-code trap, format-gate
  diagnosis recipe, and a full 4-stage run transcript (13/13 + 13/13, one
  format failure on pdfdocumentbuilder.cpp).
- `references/gh-actions-toolchain-ci-2026-08-07.md` — GitHub-hosted runner
  toolchain saga: vcpkg-needs-bootstrap (exit 127), aqt `qt_base` module-XML
  mirror flakiness, pin-vs-wildcard, archives+retry loop that finally
  worked, and the format-job-as-control triage trick.
- `references/parallel-branch-merge-conflicts-2026-08-06.md` — merging
  parallel feature branches: regenerate auto-generated files (REPO_MAP)
  instead of hand-merging; conflict resolution in CMakeLists can leave
  orphaned fragments that only the full gate catches; keep ALL additive
  exclusions/suites at merge; always re-run `ci/run-ci.sh` after resolving
  build-file conflicts.
- `references/qt-version-api-audit-2026-08-07.md` — the header-token-sweep
  method for "does this code compile on MY Qt version?" (no build): extract
  all `QClass::method` tokens, index the installed Qt headers, report the
  missing set; Qt 6.9-only QColorSpace members table; `QT_<MODULE>_LIB`
  compile-out macro semantics; `.rc`-ignored-on-Linux and `#elif`-grep-trap
  empirical findings.
- `references/vendoring-upstream-gui-dirs-2026-08-07.md` — bringing an
  upstream Qt project's GUI/app layers into a core-only fork: pin the tag,
  `git archive` extraction, 3-way parallel analysis (CMake wiring / API
  compat / integration), gate wiring (ALBDF_BUILD_GUI), compile-out of
  unprovisioned Qt modules (stub pattern), directory-level format-gate
  exclusions, build+smoke+regression verification.
- `references/appimage-qt-packaging-2026-08-07.md` — Qt AppImage build with
  linuxdeploy + qt-plugin + appimagetool in a container: FUSE-less
  (`APPIMAGE_EXTRACT_AND_RUN=1`), Debian `qt6-svg-plugins` for the missing
  icon engine, `file` command requirement, staging shape, and the
  grep-for-ERROR debugging note.
- See `pdf-text-engineering` skill `references/p6-cidtogidmap-spec-compliance.md`
  for the full case study (invalid CIDToGIDMap → wrong glyphs; Ghostscript
  as the independent oracle).
