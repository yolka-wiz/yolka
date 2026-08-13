# Upstream re-vendor EXECUTION — 3-way merge-file method (2026-08-08)

Worked example: syncing the 4 genuinely-new upstream PDF4QT core commits
(12763887, ae9958bd, ca6f467a, 7300ed2d — skip `3b99b677` TTS) into the albdf
fork's `src/` at main `a4d934b3`. The fork has NO git ancestry with upstream
(§10), so this is a file-level re-vendor, never `git merge upstream/master`.

## Preconditions

- `git fetch upstream master` (refs/remotes/upstream/*).
- Snapshot base = the upstream commit our vendored tree derives from
  (measured 2026-08-08 as ~12763887; determine by extracted-tree diff, §10).
- Classify each upstream-changed file: clean take / keep ours / 3-way merge.
  2026-08-08 outcome: 3 clean takes (pdffont.cpp, pdfpagecontentprocessor.{cpp,h}),
  4 merges (pdfdocumentbuilder.h + pdfpagecontenteditorcontentstreambuilder.cpp +
  pdfpagecontenteditorprocessor.{cpp,h}), pdfutils.* needed nothing.

## Clean takes (upstream changed, we never touched)

```bash
git show upstream/master:Pdf4QtLibCore/sources/pdffont.cpp > src/Pdf4QtLibCore/sources/pdffont.cpp
# vendored tree stores CRLF -> restore to keep diffstat sane:
sed 's/$/\r/' src/Pdf4QtLibCore/sources/pdffont.cpp > /tmp/x && mv /tmp/x src/Pdf4QtLibCore/sources/pdffont.cpp
```
Without CRLF restore: `git diff --stat` shows pdffont.cpp = 7,602 lines changed
(semantic delta = 1 line). With restore: 2 lines. ALWAYS `file <f>` to check
current line endings before deciding.

## 3-way merges (both sides changed) via git merge-file

No shared ancestry → no `git merge`. `git merge-file` performs the same 3-way
algorithm given explicit base/ours/theirs.

```bash
for f in pdfdocumentbuilder.h pdfpagecontenteditorcontentstreambuilder.cpp \
         pdfpagecontenteditorprocessor.cpp pdfpagecontenteditorprocessor.h; do
    git show 12763887:Pdf4QtLibCore/sources/$f > /tmp/base-$f
    git show upstream/master:Pdf4QtLibCore/sources/$f > /tmp/theirs-$f
    cp src/Pdf4QtLibCore/sources/$f /tmp/ours-$f
    # CRITICAL: LF-normalize ALL sides or merge-file reports a whole-file conflict
    sed 's/\r$//' /tmp/ours-$f   > /tmp/lf-ours-$f
    sed 's/\r$//' /tmp/base-$f   > /tmp/lf-base-$f
    sed 's/\r$//' /tmp/theirs-$f > /tmp/lf-theirs-$f
    git merge-file -p /tmp/lf-ours-$f /tmp/lf-base-$f /tmp/lf-theirs-$f > /tmp/lf-result-$f
    # restore CRLF if the vendored file was CRLF:
    sed 's/$/\r/' /tmp/lf-result-$f > src/Pdf4QtLibCore/sources/$f
done
```

- Symptom of missing LF-normalization: ONE conflict region spanning the whole
  file (e.g. 3,501 lines on pdfdocumentbuilder.h), because every line differs
  by `\r`. Don't hand-resolve that — normalize and re-run.
- One *small* conflict region per file after normalization is normal (both
  sides added near the same anchor, e.g. both RTL branches in
  `updateAnnotationAppearanceStreams`). Resolve keep-both.

## Verify the merge ate nothing from either side

Auto-merge silently picks a side when both touched the same lines — check:

```bash
# 1. semantic diff vs upstream master = ONLY our intended additions
git diff -w --ignore-cr-at-eol --stat \
  upstream/master:Pdf4QtLibCore/sources/pdfdocumentbuilder.h \
  src/Pdf4QtLibCore/sources/pdfdocumentbuilder.h
#   -> expect small +N only (2026-08-08: +21/+54/+101/+17, all ours)
# 2. our marker symbols survived
grep -c 'updateRtlFormFieldAppearanceStream\|m_rtlFreeTextFontData' src/Pdf4QtLibCore/sources/pdfdocumentbuilder.h
# 3. upstream marker symbols present
grep -c 'formatNumber\|isTilingPatternProcessingAllowed' src/Pdf4QtLibCore/sources/pdfpagecontent*.cpp
# 4. TTS skip guard (skip-commit verification)
grep -c QTextToSpeech src/Pdf4QtLibCore/sources/pdfdocumentbuilder.*   # = 0
```

## Format gate

Re-vendored upstream files fail `.clang-format` even untouched → add to
AUTHORED_FILES exclusion chain in `ci/run-ci.sh`:
`| grep -vE '^src/Pdf4QtLibCore/sources/pdffont\.cpp$'` (and per .h). NEVER
`clang-format -i` them. Watch the backslash-double-escape trap (§3): after any
patch, verify with `od -c` and functionally
(`echo 'src/.../pdffont.cpp' | grep -vE '<pattern>'` → rc=1 means excluded).
Fast canary: `bash ci/run-ci.sh --only-format`; then the full 4-stage gate +
`cmake --build src/build-gui -j8` + `gui-smoke.sh` (core headers are GUI deps).

## Outcome (2026-08-08)

- `a4d934b3` sync commit: 7 files, 120 insertions / 51 deletions.
- 17/17 ctest Release + 17/17 ASAN; GUI 272/272 + smoke green; format gate OK.
- Semantic diff vs upstream master shows ONLY our RTL deltas; zero TTS.
- One follow-up `a1c15b5f` (ci exclusion regex fix) after `--only-format`
  caught the 3 re-vendored files.
