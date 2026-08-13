# Upstream re-vendor into the vendored fork (git merge-file method) — 2026-08-08

Context: al-bdf-engine forks PDF4QT by SNAPSHOT-VENDORING the tree under `src/`
(no shared git ancestry — `git merge-base HEAD upstream/master` returns
nothing). Plain `git merge upstream/master` is impossible; upstream sync =
file-level re-vendor of the changed files. Verified GREEN 2026-08-08 on 4
upstream commits / 7 core files (commits `a4d934b3` + `a1c15b5f`).

## When to use
Upstream moved and you want the new core commits without losing your RTL
deltas (R#4 /ActualText, M14 appearance streams, fixed-notation, ...).

## Method (verified)

1. **Measure first — classify each upstream-changed file**:
   - **Clean take** (upstream changed, we never touched): copy the blob.
   - **3-way merge** (both sides changed): `git merge-file`.
   - **Skip** commits that are already inside our snapshot base, and any commit
     touching a compiled-out module (see TTS trap below).
   Per-file check: `git log --oneline 6bf50473..HEAD -- src/.../$f` (our count)
   vs `git log --oneline <base>..upstream/master -- Pdf4QtLibCore/sources/$f`
   (upstream count).
2. **Extract sides** (base = the upstream commit our snapshot derives from,
   e.g. `12763887` — find it by `git merge-base`-free trial: smallest `diff -r`
   against candidate commits, excluding our known-modified files):
   ```bash
   git show <base>:Pdf4QtLibCore/sources/$f        > /tmp/base-$f
   git show upstream/master:Pdf4QtLibCore/sources/$f > /tmp/theirs-$f
   cp src/Pdf4QtLibCore/sources/$f /tmp/ours-$f
   ```
3. **LF-normalize ALL THREE sides — CRITICAL.** Vendored files are CRLF;
   `git show` emits LF. `git merge-file` with mixed line endings treats the
   WHOLE file as one conflict (markers from line 1 to EOF). `sed 's/\r$//'`
   each side before merging.
4. **Merge**:
   ```bash
   git merge-file -p /tmp/lf-ours-$f /tmp/lf-base-$f /tmp/lf-theirs-$f > /tmp/lf-result-$f
   ```
   rc=1 = conflict markers remain — resolve by hand (keep BOTH sides for
   additive RTL deltas vs upstream bugfixes in different regions).
5. **Restore CRLF** if the vendored file was CRLF: `sed 's/$/\r/'`.
6. **Verify BOTH sides survived** (auto-merge can silently drop a side):
   ```bash
   grep -c '<our-marker-symbol>'  src/.../$f   # our delta still present
   grep -c '<upstream-symbol>'     src/.../$f   # upstream change present
   git diff -w --ignore-cr-at-eol --stat upstream/master:Pdf4QtLibCore/sources/$f \
       src/Pdf4QtLibCore/sources/$f   # result must be ONLY your intended additions
   ```
7. **Format-gate exclusions**: clean-take files are upstream-formatted → they
   fail our `.clang-format` even untouched. Add to the `grep -vE` chain in
   `ci/run-ci.sh` (e.g. `pdffont.cpp`, `pdfpagecontentprocessor.{cpp,h}`) —
   do NOT `clang-format -i` them (destroys vendor parity).
8. **Huge diffstat on a "clean take" = line-ending churn.** `file <path>` +
   `git diff -w --stat` to confirm the real delta is tiny (e.g. 7600-line
   stat collapsing to 1 line with `-w`); restore CRLF to match the vendored
   tree so the committed diff stays minimal.

## Traps (hit this session)

- **Patch-tool backslash double-escape — HIT AGAIN despite being documented.**
  `patch()` turns `\.` into `\\.` in the ci/run-ci.sh exclusion regex, which
  silently stops matching (grep -E sees literal backslash + any-char). Verify
  with raw BYTE counts, not repr/JSON (those lie through escaping layers):
  `python3 -c "print(open('ci/run-ci.sh','rb').read().count(b'\\\\'))"` or
  `od -c`. Fix with hex byte replace: `5c5c2e` → `5c2e` (two backslashes+dot →
  one backslash+dot). Functional check:
  `echo 'src/.../file.cpp' | grep -vE '<pattern>'` must rc=1 (= excluded).
- **TTS-like compile-out divergence**: when an upstream commit touches a module
  we compiled out (e.g. `3b99b677` Issue #397 rewrites `pdftexttospeech.cpp`
  which our stub `48d58fd8` replaced), SKIP that commit — taking it resurrects
  the unprovisioned dependency. Guard post-sync: `grep -c QTextToSpeech`.
- **Order vs in-flight work**: re-vendor AFTER merging your own feature
  branches that touch the same files (both M14 branches modified
  `pdfdocumentbuilder.cpp`; syncing before the merge interleaves conflict
  surfaces). Handoff doc's resume order applies.
- **GUI rebuild is the compat canary**: `pdfdocumentbuilder.h` is a core header
  the vendored GUI depends on — after re-vendor, build `src/build-gui`
  (272/272) + `gui-smoke.sh` to prove the merge didn't break GUI compile.

## Session record (2026-08-08)

- 4 commits taken: `12763887` (default note author), `ae9958bd` (formatNumber
  content-stream fix), `ca6f467a` (tiling-pattern no-longer-suppressed +
  image-mask bpc + stroke-colorspace fixes), `7300ed2d` (initialized-after
  warnings). Skipped: `3b99b677` (TTS).
- 7 files: 3 clean takes (`pdffont.cpp`, `pdfpagecontentprocessor.{cpp,h}`),
  4 three-way merges (`pdfdocumentbuilder.h`,
  `pdfpagecontenteditorcontentstreambuilder.cpp`,
  `pdfpagecontenteditorprocessor.{cpp,h}`).
- Result: 17/17 Release + ASAN, GUI 272/272 + smoke, format gate 44 files —
  CI: ALL GREEN.
