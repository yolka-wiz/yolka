# AppImage packaging for the albdf GUI (2026-08-07, packaging/ dir)

Build script: `packaging/build-appimage.sh` (committed `0b0c0d00`), desktop entry
`packaging/albdf-viewer.desktop`, icon `packaging/icon/albdf.png` (512×512 PNG
converted from `src/Pdf4QtEditor/app-icon.svg` with ImageMagick `convert`).

## Tooling (downloaded to `~/tools/`)

```bash
# linuxdeploy bundles ELF deps into an AppDir; the qt plugin adds Qt platform
# plugins + libs; appimagetool turns the AppDir into the AppImage.
curl -sL -o ~/tools/linuxdeploy-x86_64.AppImage \
  https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
curl -sL -o ~/tools/linuxdeploy-plugin-qt-x86_64.AppImage \
  https://github.com/linuxdeploy/linuxdeploy-plugin-qt/releases/download/continuous/linuxdeploy-plugin-qt-x86_64.AppImage
curl -sL -o ~/tools/appimagetool-x86_64.AppImage \
  https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x ~/tools/*.AppImage
```

## CRITICAL: system libs vs vcpkg libs

Check what the binaries actually link FIRST (`ldd src/build-gui/bin/Pdf4QtViewer`).
On this host the viewer links **system** Qt 6.8.2, harfbuzz, freetype, fontconfig
(`/lib/x86_64-linux-gnu/...`) — NOT the vcpkg-installed copies. linuxdeploy resolves
system libs automatically. **Do NOT blindly copy
`$VCPKG_ROOT/installed/x64-linux/lib/*.so*` into the AppDir** — the first version of
the script did that (vcpkg `installed/x64-linux/lib` may not even exist when the
toolchain uses system Qt) and had to be corrected. Only our OWN libs
(`libPdf4Qt*.so*` from `src/build-gui/lib/`) need explicit staging.

## AppDir layout (what linuxdeploy expects)

```
AppDir/
  albdf-viewer.desktop            # at AppDir root (linuxdeploy reads it)
  usr/bin/albdf-viewer|albdf-editor|albdf-pagemaster
  usr/lib/libPdf4QtLibCore/Gui/Widgets.so*
  usr/share/applications/albdf-viewer.desktop
  usr/share/icons/hicolor/512x512/apps/albdf.png
```

- Desktop entry `Exec=` must match the bundled binary name (`albdf-viewer %F`).
- `Icon=` must match the icon basename (`albdf`).
- `--desktop-file` + `--icon-file` args point linuxdeploy at them; the qt plugin is
  enabled with `--plugin qt`; `--output appimage` makes linuxdeploy call appimagetool.

## Verification before release

- `QT_QPA_PLATFORM=offscreen` smoke of the packaged binary (or the AppImage) with the
  RTL fixture — same `gui-smoke.sh` checks apply inside the AppDir.
- The AppImage format requires FUSE for direct execution on some hosts; for CI/headless
  verification use `--appimage-extract` or run the AppDir binaries directly.

## Container blockers hit during the 0.3.0 build (all fixed, 2026-08-07)

Ordered as they appear when running `build-appimage.sh` on a headless container:

1. **FUSE-less container → "No suitable fusermount binary found".** The AppImage
   *tools* (linuxdeploy/appimagetool) are themselves AppImages and self-mount via
   FUSE; containers often lack `/dev/fuse`/fusermount. Fix (committed `e667fe0a`):
   export `APPIMAGE_EXTRACT_AND_RUN=1` at the top of the build script so every
   AppImage tool self-extracts instead of mounting. Works even when `/dev/fuse`
   exists but fusermount is missing.
2. **Missing `file` command → appimagetool aborts** with
   `file command is missing but required, please install it` (after linuxdeploy
   already succeeded — the failure is in the final `--output appimage` step).
   Fix: `sudo apt-get install -y file`.
3. **qt plugin can't find the SVG icon engine** →
   `ERROR: Cannot deploy non-existing library file: .../qt6/plugins/iconengines/libqsvgicon.so`.
   On Debian this ships in its own package, **not** `qt6-svg-dev` or
   `libqt6svg6`: `sudo apt-get install -y qt6-svg-plugins`. Install it before
   building (the GUI's icons are SVG so the AppImage genuinely needs it).
4. **AppImage bundles ONLY the `xcb` platform plugin by default.** A launch with
   `QT_QPA_PLATFORM=offscreen` fails with "Could not find the Qt platform plugin
   \"offscreen\"" even though xcb IS present — that's expected and fine for a
   desktop bundle. **Trap:** if the SHELL has `QT_QPA_PLATFORM=offscreen` exported
   (common after headless testing), the AppImage launch fails confusingly; `unset
   QT_QPA_PLATFORM` before testing. Verify a desktop AppImage under xvfb:
   ```bash
   unset QT_QPA_PLATFORM
   APPIMAGE_EXTRACT_AND_RUN=1 xvfb-run -a bash -c \
     './albdf-0.3.0-x86_64.AppImage <fixture.pdf> & PID=$!; sleep 6; \
      kill -0 $PID && echo "STILL RUNNING (SUCCESS)"; kill $PID; wait $PID'
   ```
   rc 143 (SIGTERM) after "STILL RUNNING" = the app launched and stayed alive —
   success. ("The X11 connection broke" on teardown is just xvfb shutting down.)
