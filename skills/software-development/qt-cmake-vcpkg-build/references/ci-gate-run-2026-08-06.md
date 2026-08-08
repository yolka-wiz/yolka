# albdf local CI gate — run layout & 2026-08-06 verification

## Gate stages (ci/run-ci.sh)

Bare invocation runs all 4 stages. Flags: --skip-asan, --skip-format,
--skip-release, --only-format. Exit 0 = all green, 1 = any stage failed.

1. **Release configure+build**: `cmake -S . -B build -G Ninja
   -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/... `
   `-DALBDF_BUILD_TESTS=ON` → /tmp/ci-build.log. Runs from `src/`.
2. **offscreen ctest**: `QT_QPA_PLATFORM=offscreen ctest --test-dir build
   --output-on-failure` → /tmp/ci-ctest.log.
3. **ASAN/UBSAN**: fresh `build-asan` Debug configure (sanitizer flags on
   C/CXX flags + EXE/SHARED linker flags) → /tmp/ci-asan-cfg.log, build →
   /tmp/ci-asan-build.log, ctest with
   `LD_LIBRARY_PATH=$SRC/build-asan/lib`,
   `ASAN_OPTIONS=detect_leaks=0:abort_on_error=1`,
   `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1` →
   /tmp/ci-asan-ctest.log. Fresh build dir every run = full rebuild =
   the long pole (15-40 min).
4. **clang-format gate**: authored files = `git diff --name-only
   6bf5047..HEAD -- '*.cpp' '*.h'` minus excludes
   (pdftoolabstractapplication.{cpp,h}, main.cpp,
   pdfpagecontenteditorprocessor.{cpp,h},
   pdfpagecontenteditorcontentstreambuilder.{cpp,h}, pdftextlayout.cpp).
   Vendored upstream files intentionally NOT formatted (cherry-pick
   hygiene); upstream-derived files only MODIFIED are excluded too.

## Run pattern

```bash
export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg   # script default /workspace/vcpkg is WRONG on this host
cd /home/agent/workspace/wt-core-redaction
bash ci/run-ci.sh    # background=true + notify_on_complete; do NOT foreground
```

## Exit-code trap (hit 2026-08-06)

`bash ci/run-ci.sh 2>&1 | tee /tmp/ci-run.log` → process tool reports
exit 0 even when the gate FAILED, because tee is the last pipe element and
pipefail is off. Reliable signals: the script's final line
`CI: ALL GREEN` / `CI: FAILED`, or
`bash -c 'set -o pipefail; bash ci/run-ci.sh | tee log; echo "real=$?"'`.

## Format-gate diagnosis

```bash
clang-format --dry-run --Werror <file>     # names the violation line
clang-format <file> | diff <file> -        # exact reflow to apply
```

Typical violations: include reordering (clang-format re-sorts adjacent
includes) and case-brace collapse (`case 1:` newline `{` → `case 1: {`).
A gate-red format failure requires a NEW fix commit — the branch cannot
merge until green (AGENTS.md §6, CONTRIBUTING.md).

## 2026-08-06 result (branch m10/core-redaction @ 558a267, read-only run)

- Stage 1: PASS (incremental — src/build existed)
- Stage 2: **13/13 passed, 0 failed**, 4.69s — UnitTestsRedact 0.56s,
  UnitTestsPageOps 0.70s, SmokeCli 0.85s
- Stage 3: **13/13 passed, 0 failed**, 29.46s — no ASAN/UBSAN errors;
  page-ops determinism tests stable under ASAN (post-e79bc06)
- Stage 4: **FAIL** — 1 of 41 authored files UNFORMATTED:
  `src/Pdf4QtLibCore/sources/pdfdocumentbuilder.cpp`, last touched by
  e79bc06 (deterministic CreationDate/ModDate fix): include order
  (pdfencoding.h/pdfobjectutils.h) + 4 case-brace blocks (lines ~77-91).
- Overall: CI: FAILED (real exit 1; pipeline masked as 0 — see trap above)
- git status stayed clean throughout (read-only verification contract).
