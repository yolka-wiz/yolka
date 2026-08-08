# GUI CI stage (`ci/run-ci.sh --gui`) — implementation record 2026-08-07

M12 Phase 2 (GUI-restore CI). Commit `7dc95d50` on branch `m12/gui-ci`
(PR #7 side branch; NOT pushed — orchestrator pushes after review).
Diff: `ci/run-ci.sh` + `.github/workflows/ci.yml` + `CONTRIBUTING.md`,
3 files, +68/−1.

## What changed

- `ci/run-ci.sh`: new `--gui` flag (+ `ALBDF_CI_STAGE=gui` env alternative) sets
  `GUI=1`. After `cd "$SRC_DIR"`, an `if [ "$GUI" -eq 1 ]` block runs the gui
  stage and `exit "$FAILED"`s BEFORE the headless stages — the bare invocation
  and all existing flags are untouched:
  - configure: `cmake -S . -B build-gui -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE="$VCPKG_TOOLCHAIN" -DALBDF_BUILD_GUI=ON` → `/tmp/ci-gui-build.log`
  - build: `cmake --build build-gui -j"$(nproc)"` → same log
  - smoke: `QT_QPA_PLATFORM=offscreen bash "$REPO_DIR/src/tests/gui-smoke.sh"` → `/tmp/ci-gui-smoke.log`
  - prints `CI: ALL GREEN` / `CI: FAILED`; exit 0/1.
- `.github/workflows/ci.yml`: `gui` job (ubuntu-24.04, `continue-on-error: true`):
  checkout `fetch-depth: 0` → setup-toolchain → `sudo apt-get update && sudo
  apt-get install -y xvfb` → `run: bash ci/run-ci.sh --gui`. No toolchain change
  needed: Qt Widgets/PrintSupport/Concurrent are all inside aqt's qtbase archive
  (setup-toolchain already installs qtbase+qtsvg and exports
  CMAKE_PREFIX_PATH/LD_LIBRARY_PATH).
- `CONTRIBUTING.md`: one line documenting `bash ci/run-ci.sh --gui`.
- `scripts/gen-repo-map.py` produced no REPO_MAP.md change (nothing to commit).

## Local verification (exact transcript, exit 0)

`cd /home/agent/workspace/al-bdf-engine && export VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg && bash ci/run-ci.sh --gui`

```
=== gui: configure + build (Release, ALBDF_BUILD_GUI=ON) ===

=== gui: smoke (headless — offscreen, xvfb fallback) ===
OK: viewer = /home/agent/workspace/al-bdf-engine/src/build-gui/bin/Pdf4QtViewer
OK: fixture = /home/agent/workspace/al-bdf-engine/src/tests/fixtures/gui-rtl.pdf (db787c3005a4a3275ecbbda5da0458d5fd78ad5345b465e37da9577f258f7006)
OK: --help exits 0 (offscreen)
OK: [offscreen] viewer stayed alive 8s with the RTL fixture open and exited cleanly on SIGTERM

CI: ALL GREEN
```

- Configure 0.8s on the warm cache; `ninja: no work to do.` (build-gui already
  current from M12 WS5). `-- Could NOT find XKB` / `-- Could NOT find Cups`
  lines are benign optional-component notices, not errors.
- Smoke ran fully offscreen — no xvfb fallback needed (xvfb-run is at
  `/usr/bin/xvfb-run` locally if ever needed).
- Also verified: `ALBDF_CI_STAGE=gui bash ci/run-ci.sh` → identical green output;
  `bash ci/run-ci.sh --skip-release --skip-asan --skip-format` (no flag) does NOT
  run the gui stage → headless gate untouched.
- Gotcha: the stage's configure line omits `-DALBDF_BUILD_TESTS`. The pre-existing
  local build-gui dir (M12) had tests ON, so the first `--gui` run flips them OFF:
  ninja drops the test targets (no recompile of core/GUI objects), and the stale
  `UnitTests*` binaries linger in `bin/` but are no longer maintained by that
  build dir. Harmless — the smoke only needs `Pdf4QtViewer`.

## Verification-method notes (scripted ad-hoc check, 13/13 pass)

Covered: `--gui` exit 0 + ALL GREEN + smoke OK lines + no FAILED lines; env
selector; no-flag run skips the gui stage; `bash -n ci/run-ci.sh`; pyyaml parse
of ci.yml with the `gui` job present; gui job block has continue-on-error +
xvfb install + `run: bash ci/run-ci.sh --gui`.

**Check-integrity lesson:** an initial "YAML parse error" was a FALSE negative —
pyyaml is simply not installed in the system python (`ModuleNotFoundError` is
not a syntax error). Fix: install one-off verification deps into a cleanable
target (`python3 -m pip install --quiet --target /tmp/hermes-verify-pyyaml
pyyaml`, run with `PYTHONPATH=/tmp/hermes-verify-pyyaml`, `rm -rf` after) rather
than polluting the env. Also re-audit your own assertions: a `count(...) == 1`
check failed only because benchmark+fuzz already carry `continue-on-error: true`
(3 real flags + 2 header-comment mentions = 5 total). Verify the check before
blaming the file.

`ci/run-ci.sh` leaves `/tmp/ci-gui-build.log` + `/tmp/ci-gui-smoke.log` behind —
standard per-stage logs, same convention as `/tmp/ci-build.log`.
