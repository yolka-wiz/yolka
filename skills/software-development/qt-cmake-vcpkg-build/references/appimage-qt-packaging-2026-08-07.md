# Qt AppImage packaging in a FUSE-less container (2026-08-07)

Worked example for pitfall 18 in SKILL.md. Building an AppImage of a Qt GUI
app (albdf Viewer/Editor/PageMaster) with linuxdeploy +
linuxdeploy-plugin-qt + appimagetool — the tools are themselves AppImages.

## Tool acquisition

```bash
mkdir -p ~/tools && cd ~/tools
curl -sL -o linuxdeploy-x86_64.AppImage \
  https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
curl -sL -o appimagetool-x86_64.AppImage \
  https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
curl -sL -o linuxdeploy-plugin-qt-x86_64.AppImage \
  https://github.com/linuxdeploy/linuxdeploy-plugin-qt/releases/download/continuous/linuxdeploy-plugin-qt-x86_64.AppImage
chmod +x *.AppImage
```

## The three sequential blockers

1. **FUSE**: `Error: No suitable fusermount binary found on the $PATH` /
   `$FUSERMOUNT_PROG not set` / `Cannot mount AppImage`. Even with
   `/dev/fuse` present, the `fusermount` binary may be missing.
   Fix in the packaging script (permanent):
   `export APPIMAGE_EXTRACT_AND_RUN=1`
2. **Qt SVG icon engine missing**: linuxdeploy qt-plugin fails with
   `ERROR: Cannot deploy non-existing library file:
   /usr/lib/x86_64-linux-gnu/qt6/plugins/iconengines/libqsvgicon.so`.
   Debian: `qt6-svg-dev` ≠ runtime plugin. Fix:
   `sudo apt-get install -y qt6-svg-plugins`
3. **`file` command missing**: appimagetool fails with
   `file command is missing but required, please install it` (exit 1 from
   the appimage output plugin). Fix: `sudo apt-get install -y file`

## Script shape that worked

- Stage `AppDir/usr/bin/<app>` (renamed thin mains) + `AppDir/usr/lib` with
  the project's OWN libs only (`cp -a build/lib/libPdf4Qt*.so*`).
- Desktop entry in `AppDir/usr/share/applications/` + copy into AppDir root
  (linuxdeploy wants it there too); 512×512 PNG icon in
  `usr/share/icons/hicolor/512x512/apps/` (convert the app's SVG with
  ImageMagick `convert -background none app-icon.svg -resize 512x512`).
- `linuxdeploy --appdir AppDir --executable ... --desktop-file ...
  --icon-file ... --plugin qt --output appimage`
- DO NOT copy vcpkg `installed/*/lib/*.so*` wholesale — the GUI links
  SYSTEM harfbuzz/freetype (verify with `ldd`), and linuxdeploy resolves
  system libs itself.

## Debugging notes

- linuxdeploy qt-plugin output is extremely verbose
  (`[qt/stdout] Deploying ...` per dependency). The failure is the LAST
  `ERROR:` line — grep for `ERROR` not `Deploying`.
- `APPIMAGE_EXTRACT_AND_RUN=1` also speeds up repeated tool invocations
  (no mount/unmount per call) and is the right default for CI.
