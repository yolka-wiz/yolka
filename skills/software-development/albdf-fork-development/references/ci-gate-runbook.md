# Local CI gate runbook (ci/run-ci.sh) — verified green run

Verified on branch `m10/fix-render-args` @ `861335b` (Aug 2026), worktree
`/home/agent/workspace/wt-fix-render`, when GitHub Actions runners were down.
Gate finished in a few minutes because `src/build` was already up to date;
a cold run with a fresh ASAN build takes 15-40 min.

## Launch (background, notify_on_complete)

```bash
export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg   # script's default /workspace/vcpkg is WRONG here
cd /home/agent/workspace/wt-fix-render
bash ci/run-ci.sh > /tmp/ci-run.log 2>&1; echo "CI_EXIT_CODE=$?"
```

- Run via terminal tool with `background=true, notify_on_complete=true` — the
  foreground timeout (600s) is too short for the ASAN stage.
- Pre-flight sanity: `ls` the vcpkg toolchain
  (`/home/agent/vcpkg-cache/vcpkg/scripts/buildsystems/vcpkg.cmake`), check which
  build dirs exist (`src/build` yes, `src/build-asan` absent on a fresh gate),
  and confirm `git status --short` is clean before launching.
- Old `/tmp/ci-*.log` files are overwritten by the script — no need to clean them.

## Stage structure & log files

| Stage | What runs | Log file |
|---|---|---|
| 1/4 | Release configure+build (Ninja, vcpkg toolchain, ALBDF_BUILD_TESTS=ON) | /tmp/ci-build.log |
| 2/4 | `QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure` | /tmp/ci-ctest.log |
| 3/4 | ASAN/UBSAN Debug configure+build (build-asan) then ctest | /tmp/ci-asan-cfg.log, /tmp/ci-asan-build.log, /tmp/ci-asan-ctest.log |
| 4/4 | clang-format gate on authored files (diff 6bf5047..HEAD minus exclusions) | stdout → /tmp/ci-run.log |

ASAN stage env set by the script: `ASAN_OPTIONS=detect_leaks=0:abort_on_error=1`,
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.

## Verification (exact expected output from the green run)

```bash
cat /tmp/ci-run.log        # expect 4 stage headers, "clang-format gate OK (40 files)", "CI: ALL GREEN"
grep -c FAILED /tmp/ci-run.log   # → 0
tail -8 /tmp/ci-ctest.log  # → "100% tests passed, 0 tests failed out of 13"
tail -8 /tmp/ci-asan-ctest.log   # → "100% tests passed, 0 tests failed out of 13"
tail -2 /tmp/ci-asan-build.log   # → "[178/178] Linking ..." (build completed)
cd <repo> && git status --short  # → empty (no repo modifications)
```

`CI_EXIT_CODE=0` ⇔ all four stages green. `CI: FAILED` ⇒ exit 1; the script
prints `tail -N` of the failing stage's log to stdout, which lands in
`/tmp/ci-run.log`.

## Notes

- `process wait` blocks ≤180s per call — after launching, poll once to confirm
  stage 3 configure succeeded, then rely on the completion notification and
  re-wait as needed.
- Stage-selection flags: `--skip-release` (assumes green Release build; hosted-CI
  ASAN job), `--skip-asan`, `--skip-format`, `--only-format` (hosted-CI format job).
- The gate does NOT touch `db/albdf.db`; closing DB tasks stays the orchestrator's job.
