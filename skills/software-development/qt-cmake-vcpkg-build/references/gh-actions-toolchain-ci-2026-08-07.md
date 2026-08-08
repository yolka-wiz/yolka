# GitHub Actions toolchain for vcpkg + Qt — CI case study (2026-08-07)

Hosting the albdf vcpkg-manifest + Qt 6.8 build on GitHub-hosted runners
took SEVEN consecutive failing runs. Each failure was a real config bug,
masked in sequence by the GitHub Partial System Outage (runs queued for
hours, so the first completed run exposed every layer at once).

## The failure signature

Every job died inside the composite `setup-toolchain` step ~2s in, before
any build. `gh run view <id> --json jobs` showed all jobs failing; the
`clang-format gate` job was the ONLY one succeeding (it skips Qt/vcpkg via
`install-qt: false`) — that asymmetry is the triage control that isolates
toolchain setup from code.

## Layer 1: vcpkg clone ≠ usable vcpkg (exit 127)

Composite action did:
```bash
git clone --depth 1 --branch "${ALBDF_VCPKG_REF}" https://github.com/microsoft/vcpkg.git "${VCPKG_ROOT}"
"${VCPKG_ROOT}/vcpkg" version
```
Failed: `line 2: .../vcpkg/vcpkg: No such file or directory` (exit 127).

**Root cause:** the `vcpkg` executable is NOT in the repo — it is produced
by `bootstrap-vcpkg.sh`. Locally this never bites because the pre-existing
vcpkg cache tree was bootstrapped long ago (bootstrap-vcpkg.sh exists, and
a built `./vcpkg` binary sits next to it). CI's fresh clone is a source
tree only.

**Fix:**
```bash
"${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics
"${VCPKG_ROOT}/vcpkg" version
```

## Layer 2: aqt `qt_base` module-XML failure

After bootstrap, jobs failed with:
```
ERROR : The packages ['qt_base'] were not found while parsing XML of package information!
```
from `jurplel/install-qt-action` (which shells out to `python3 -m aqt`).

**Root cause:** aqt resolves the base Qt package name through an
Updates.xml fetch; for Qt 6.8 the base archive entry (`qt_base`) is absent
from the module XML aqt parses on the mirror/CDN edge the GH runner
reaches. Known upstream flakiness — miurahr/aqtinstall#769 and
jurplel/install-qt-action#231.

**Key diagnostic discipline:** the SAME aqt 3.3.0 + SAME command works
locally (routes via `mirror.maeen.sa` / `ftp.fau.de`) and fails on GH.
Local success proves nothing about the runner. Match on the exact error
text, not on "it worked in my shell".

### Sub-attempts that did NOT fix it (each removed one variable)
- Removing `modules: qtsvg` → error changed to `['qt_base']` alone.
- Pinning `6.8.3` instead of `6.8.*` → same `qt_base` error.
- Adding `archives: qtbase qtsvg` to the action → same `qt_base` error
  (aqt fetches the module XML for repo layout even when told specific
  archives).

### The fix that worked: direct aqt + retry loop
Replace `jurplel/install-qt-action` with a shell step:
```bash
set -euo pipefail
python3 -m pip install --quiet "aqtinstall==3.3.*"
QT_DIR="${RUNNER_TEMP}/qt"
for attempt in 1 2 3; do
  echo "== aqt install attempt ${attempt}/3 =="
  if python3 -m aqt install-qt linux desktop 6.8.3 linux_gcc_64 \
      --archives qtbase qtsvg \
      --outputdir "${QT_DIR}" \
      --timeout 30; then
    break
  fi
  [ "${attempt}" -lt 3 ] && sleep 10
done
QMAKE="$(find "${QT_DIR}" -path '*/bin/qmake' -type f | head -1)"
[ -n "${QMAKE}" ] || { echo "qmake not found after Qt install"; exit 1; }
QT_ROOT_DIR="$(dirname "$(dirname "${QMAKE}")")"
echo "CMAKE_PREFIX_PATH=${QT_ROOT_DIR}" >> "${GITHUB_ENV}"
```
Why it works: the retry loop lets aqt rotate mirrors between attempts, so a
flaky CDN edge is retried instead of aborting the job. Pinning the exact
version (`6.8.3`) removes wildcard resolution from the flaky XML path.

Also install Qt's runtime xcb deps (the old action's `install-deps: true`
provided them):
```bash
sudo apt-get install -y --no-install-recommends cmake ninja-build \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 \
    libgl1-mesa-dev
```

## Layer 3: verify Qt actually got installed

Locate qmake the same way install-qt-action does:
`find <QT_DIR> -path '*/bin/qmake' -type f | head -1` — for
`--outputdir ${RUNNER_TEMP}/qt` it lands at
`${RUNNER_TEMP}/qt/6.8.3/gcc_64/bin/qmake`.

## Layer 4: Qt 6.8.3 prebuilt needs ICU 73 (ubuntu-24.04 ships 74)

With setup green, jobs actually built and then failed:
```
.../libexec/rcc: error while loading shared libraries: libicui18n.so.73: cannot open shared object file
```
(also libicuuc.so.73, libicudata.so.73).

**Root cause:** Qt's online binaries are built on RHEL against ICU 73. NO
distro packages ICU 73 (Ubuntu archives have 71/72/74; Debian stable jumped
72→74/76). **Do NOT symlink ICU 74→73** — ICU's major version IS the ABI
boundary; Qt fails with `undefined symbol: ucnv_reset_73`.

**Fix (verified, ~1 min): build ICU 73 from the upstream release tarball**
in the action, then export LD_LIBRARY_PATH:
```bash
curl -sL "https://github.com/unicode-org/icu/releases/download/release-73-2/icu4c-73_2-src.tgz" -o /tmp/icu73.tgz
tar xzf /tmp/icu73.tgz -C /tmp
cd /tmp/icu/source
./configure --prefix=/tmp/icu-build --disable-tests --disable-samples --disable-dyload
make -j"$(nproc)"
make install
echo "LD_LIBRARY_PATH=/tmp/icu-build/lib:${LD_LIBRARY_PATH:-}" >> "${GITHUB_ENV}"
```
Verify locally first: `LD_LIBRARY_PATH=/tmp/icu-build/lib <qt>/libexec/rcc --version`
must print the Qt version.

### ORDERING TRAP (the run-7 → run-8 difference)
**Build ICU BEFORE the aqt Qt install.** aqt's post-install step EXECUTES
qmake to verify the install ("Patching .../bin/qmake"), and that qmake needs
ICU 73 on LD_LIBRARY_PATH. Run 7 put the ICU step AFTER the Qt step and
still failed with the same missing-lib error — because the qmake check runs
inside the Qt step, before the later ICU step ever executes. GITHUB_ENV
lines apply to subsequent steps, so the sequence must be:

1. Build ICU 73 → write `LD_LIBRARY_PATH=/tmp/icu-build/lib:...` to GITHUB_ENV
2. Install Qt (env already active → aqt's qmake check passes)
3. Append `${QT_ROOT_DIR}/lib` to LD_LIBRARY_PATH for the build steps

Verified locally: aqt install with ICU 73 already on LD_LIBRARY_PATH
completes and patches qmake OK; without it, qmake dies immediately after
"Finished installation of qtbase".

The local dev container never hits this because it uses SYSTEM Qt (apt
qt6-base-dev), built against the distro's current ICU — the aqt prebuilt is
the only path that exposes it.

## Layer 5: missing system headers (fontconfig/freetype)

With the toolchain fully green, the first REAL project-compile failure was:
```
pdffont.cpp:53:10: fatal error: fontconfig/fontconfig.h: No such file or directory
```
**Fix:** add the dev packages to the toolchain apt step:
```bash
sudo apt-get install -y --no-install-recommends cmake ninja-build \
    ... libfontconfig1-dev libfreetype-dev
```
Check what system headers the project includes before finalizing the apt
list (`grep -rn '#include <' src/ | grep -v Qt | sort -u`), and mirror what
the working local machine has (`dpkg -l | grep libfontconfig`).

## Layer 6: benchmark false-failure from locale thousands separators

With toolchain + build green (gate/asan/format all success), the last
non-gating job (`benchmark`, continue-on-error) failed with:
```
op=info,ms=29,ok=0,pages=1,000
op=fetch_text,ms=61,ok=1   ... (all ms tiny, far under 5000 threshold)
result=FAIL,ops=5,failed=1,max_ms=89
benchmark: FAIL (policy: every op must be <= 5000 ms)
```
The tell: `max_ms` tiny + `failed=N` high = assertion/parse bug, NOT a perf
regression.

**Root cause:** the 1000-page fixture's `info` output prints
`Page count         1,000` (comma from locale-formatted output). The script
did `awk '/Page count/ {print $3; exit}'` and compared against `"1000"` —
mismatch → `ok=0`. Small fixtures (5-page multipage) print `5` (no comma),
so the script passes locally on small docs and fails only on the big one.

**Fix:** strip commas in the parse, for BOTH the page count and the search
matches count:
```bash
PAGES="$(printf '%s\n' "$OP_OUT" | awk '/Page count/ {gsub(/,/, "", $3); print $3; exit}')"
MATCHES="$(printf '%s\n' "$OP_OUT" | awk '/^[ \t]*[0-9,]+[ \t]*$/ {gsub(/,/, "", $1); print $1; exit}')"
```
Also make `time_op` self-contained headless:
```bash
OP_OUT="$(QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$@" 2>&1)"; OP_CODE=$?
```
Without it, a local run with no exported `QT_QPA_PLATFORM` makes the binary
abort exit 134 (SIGABRT) and EVERY op reports `ASSERTION FAILED` — CI's
job-level env hides this, which is why the script looked fine in CI until
the comma bug surfaced.

Verify locally on the big fixture before pushing:
`bash scripts/benchmark.sh --work-dir /tmp/bench-fixed` → `result=PASS,
ops=5, failed=0`.

## CI failure triage order (reusable)

1. Get the exact failing line: `gh run view <id> --log-failed`.
2. exit 127 + `No such file or directory` → missing bootstrap/executable
   step (vcpkg, other tools).
3. aqt/XML parse error → mirror flakiness. Fix with retry; never conclude
   from a local re-run that the CI config is fine.
4. `clang-format gate` succeeding while build jobs fail → the format job
   skips the whole toolchain (`install-qt: false`), so it is the control
   that isolates setup from build. Format green + build red = setup layer.
5. Qt tool (`rcc`/`qmake`) fails on a shared library → Qt-built-against-ICU
   mismatch; build the exact ICU from source, BEFORE the Qt install.
6. Project source fails on a missing header → add the dev package to the
   apt step (fontconfig, freetype, etc.).

## Git workflow note

Each fix was a small commit to `.github/actions/setup-toolchain/action.yml`
pushed to main, triggering a fresh `push → main` run (the workflow has
`on: push: branches: [main]`). Fixes shipped: `67e1ff9` (bootstrap),
`89c7eb7` (drop invalid module), `a9fb2ce` (pin version), `231e36d`
(archives + retry + xcb deps), `7ac1b0f` (ICU build), `52db103` (ICU moved
BEFORE Qt install — the ordering fix), `26318ce` (fontconfig/freetype).
The retry-loop commit was the one that got jobs actually building; the ICU
ordering commit got them past aqt's qmake check; the fontconfig commit got
the first real compile.
