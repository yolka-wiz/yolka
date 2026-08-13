# Upstream sync audit — pulling new commits into the fork (2026-08-08)

Session: "check project status, list what changed on the original repo, could we pull the
new commits without ruining the project?" Answer: YES with a controlled file-level
re-vendor; NO to `git pull` (no ancestry).

## Project status at audit time

- `main` @ `69e79af4`, working tree clean; two unmerged M14 worktrees in flight:
  `wt-m14-forms` (`m14/form-field-ap`), `wt-m14-freetext` (`m14/freetext-ap`).
- Upstream head `3b99b677` (2026-08-06, Issue #397 TTS), **23 commits** past v1.6.0.0 tag.

## Structural fact (the headline)

`git merge-base HEAD upstream/master` → EMPTY (rc=1). The fork has NO shared ancestry:
root commit `caf795b7` (2026-08-03) scaffolded fresh, PDF4QT vendored as a file snapshot
into `src/` at M1 (`6bf50473`, upstream state ≈ 2026-07-12, best-match candidate
`53cac7ce` at 18 diff-lines). `git pull`/`git merge upstream/master` is impossible —
**any sync is a file-level re-vendor** (copy upstream file versions into `src/`, re-apply
our deltas). The "1,414 behind" number from the earlier audit is a diff-level estimate,
not an ancestry gap.

## What's genuinely new upstream since our snapshot

Only 4 core commits + 1 GUI commit post-date our vendored base:

| Commit | Date | Change | Touches our files? |
|---|---|---|---|
| `12763887` | 08-05 | Issue #412 — default Note author name | no |
| `ae9958bd` | 08-06 | minor bugfixes (incl. exponential-notation number fix) | yes (contentstreambuilder) |
| `ca6f467a` | 08-06 | Issue #238 — tiling patterns no longer suppressed (real bug fix) | yes (editorprocessor trio) |
| `7300ed2d` | 08-07 | Fix initialized-after warnings (#406) | yes (pdffont.cpp, ours untouched) |
| `3b99b677` | 08-06 | Issue #397 — TTS no-audio fix (GUI only) | ⚠️ SKIP — rewrites `pdftexttospeech.cpp`, resurrects Qt TextToSpeech dep |

Plus ~31 GUI-dir files changed since the v1.6.0.0 tag (GUI was vendored from that tag in
M12); unrelated to RTL work.

## Conflict surface (measured, CRLF-insensitive per-file diff)

**True both-sides conflicts (3 files):**
- `pdfpagecontenteditorcontentstreambuilder.cpp` — upstream: `formatNumber` helper
  (exponential-notation fix); ours: R#4 `/ActualText` capture + fixed-notation floats.
  Low overlap (different regions).
- `pdfpagecontenteditorprocessor.cpp` — upstream: Issue #238 tiling decomposition; ours:
  R#4 marked-content capture + control-char fonts. Additive.
- `pdfpagecontenteditorprocessor.h` — upstream: `isTilingPatternProcessingAllowed`
  virtual; ours: R#4 override. Additive (new virtual).

**Clean-take (4):** `pdfdocumentbuilder.h`, `pdffont.cpp`, `pdfpagecontentprocessor.cpp/.h`
(upstream changed, we didn't).

**Keep-ours (no upstream change):** `pdfdocumentbuilder.cpp` (deterministic dates),
`pdfpagecontenteditorcontentstreambuilder.h`, `pdfutils.cpp` (render range/DPI bounds).

## Recommended sync sequence

1. Merge M14 worktrees to main FIRST — `wt-m14-freetext` modifies `pdfdocumentbuilder.cpp`
   which the sync also touches; syncing before the merge interleaves WIP.
2. Take `12763887` + `7300ed2d` (trivial, zero conflict).
3. Take `ae9958bd` + `ca6f467a` with manual 3-way merge on the `pdfpagecontenteditor*`
   trio — or re-apply our 3 deltas onto upstream's new file versions (cleaner).
4. SKIP `3b99b677` / re-apply the TTS compile-out if re-vendoring GUI.
5. Full gate: `ci/run-ci.sh` + `--gui` before push.

## Risk table (delivered to user)

| Severity | Issue |
|---|---|
| 🔴 | Syncing now interleaves with unmerged M14 WIP — do M14 merge first |
| 🟠 | TTS commit must be excluded or GUI re-build breaks on TextToSpeech |
| 🟡 | After `ca6f467a`, `isTilingPatternProcessingAllowed` (max 512 tiles) may need GUI call-site check |
| 🟢 | No CLI/test impact — upstream core changes don't touch PdfTool or RTL pipeline |

## Trap log (this session)

- **Tree-vs-tree `git diff` with differing path prefixes is garbage**: `git diff
  v1.6.0.0:Pdf4QtLibCore src/Pdf4QtLibCore` → 384 files / 549k insertions for a
  CRLF-only diff; `--name-only` floods the whole tree. Use `git archive` + `diff -r -q
  --strip-trailing-cr` on extracted trees instead.
- **Relative-path silent-zero bug**: `diff -r ... our-core/...` run from the repo dir
  (where `our-core` doesn't exist) yields "0 diff-lines" for EVERY candidate → bogus
  all-match. Absolute paths only.
- **Nonexistent-path false match**: `git diff <ref>:pdf4qtlibcore/...` (lowercase —
  path doesn't exist upstream) prints nothing, rc=0 → `$(...)` check "matches" the first
  candidate. Verify paths with `git ls-tree --name-only <ref> <dir>` first.
- CRLF: upstream stores CRLF; `--ignore-cr-at-eol` (with `-w`) mandatory for semantic
  reads; plain stat/raw output untrustworthy.
