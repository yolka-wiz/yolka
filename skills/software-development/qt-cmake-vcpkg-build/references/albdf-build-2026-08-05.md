# albdf build & test session (2026-08-05)

Concrete evidence for the `qt-cmake-vcpkg-build` workflow on
`yolka-wiz/al-bdf-engine` (project renamed `pdfedit`→`albdf` in the same day's
work).

## Environment

- Debian 13 (trixie) x86_64, 8 CPU / 15 GB RAM, Incus container
- apt already on Aliyun mirror; g++ 14.2.0, Python 3.13.5 present
- NO cmake, ninja, Qt6, vcpkg initially (fresh container)

## System packages installed (apt, Aliyun)

```
build-essential cmake ninja-build pkg-config git ca-certificates curl unzip zip \
g++ clang clang-format \
qt6-base-dev qt6-svg-dev qt6-tools-dev qt6-translations-l10n \
libfontconfig1-dev fonts-liberation ccache
```

Result: Qt6 **6.8.2** (qt6-base-dev 6.8.2+dfsg-9+deb13u2).

## vcpkg bootstrap failure + fix

- First attempt ran bootstrap **in parallel** with the apt install → failed
  with a misleading "Could not find zip" style message. Root cause: the apt
  install hadn't finished providing curl/unzip/zip when bootstrap checked.
- Re-ran bootstrap after apt completed → still failed on **zip** (not
  installed by the first apt list, which had `unzip` but not `zip`).
- Fix: `sudo apt-get install -y zip`, then
  `bash bootstrap-vcpkg.sh -disableMetrics` → OK, vcpkg
  **2026-07-27-98d7cb0cf1f4686a3e43aa5672b6230c1d56bce8**.

**Lesson:** apt list must include `zip`; sequence apt → bootstrap; don't
parallelize them.

## Configure (first run = vcpkg manifest builds)

```
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE=/home/agent/vcpkg-cache/vcpkg/scripts/buildsystems/vcpkg.cmake \
  -DVCPKG_OVERLAY_PORTS=/home/agent/workspace/al-bdf-engine/src/vcpkg/overlays \
  -DALBDF_BUILD_TESTS=ON
```

- Took **396 s** (configuring done) — built from source: asmjit, blend2d,
  brotli, bzip2, freetype, fribidi, harfbuzz, lcms, libjpeg-turbo, libpng,
  openjpeg, openssl (3.6.3), tbb, vcpkg-cmake.
- Overlay ports (`src/vcpkg/overlays`) were required for blend2d/asmjit.
- Deps land in `src/build/vcpkg_installed/x64-linux/` (manifest mode).

## Build + tests

- `cmake --build build` → **167/167 targets**, incl. `bin/albdf` and all
  UnitTests.
- `QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure`
  → **11/11 passed** (unit, image-optimizer, font-encoding, recognize-text,
  delete-object, add-text, rtl-add-text, search-text, golden, form-signature,
  smoke-cli). Total 3.09 s.
- `QT_QPA_PLATFORM=offscreen bash src/tests/smoke.sh src/build/bin/albdf src/tests/fixtures`
  → **34/34 passed**.

## CLI round-trip (RTL differentiator)

```
QT_QPA_PLATFORM=offscreen src/build/bin/albdf --version   → albdf 0.1.0
add-text  blank.pdf out.pdf --page 1 --x 72 --y 700 --text "سلام دنیا" \
          --size 24 --rtl --font src/tests/fonts/Vazirmatn-Regular.ttf --lang fa
          → "Added RTL text 'سلام دنیا' to page 1 at (72, 700)."
search-text out.pdf "سلام" → 1 match, page 1, bbox 140.098 700 58.8398 21.7734
```

Notes:
- Match output shows the **visual-order** string (`ملس`) — expected: PDF
  content streams store glyphs visually; `/ActualText` carries logical text.
  Do NOT treat reversed RTL output in search/render as a bug.
- `render` rejects `--image-output`; the real flag is `--image-output-dir`
  (check `<cmd> --help`, don't trust README examples).
- First headless invocation aborts with an xcb "could not connect to display"
  error unless `QT_QPA_PLATFORM=offscreen` is exported — expected Qt behavior,
  not a build failure.

## Artifacts

- `/home/agent/workspace/albdf-test-out/` — rendered PNG + RTL test PDF +
  delete-object output PDF (session copies).
