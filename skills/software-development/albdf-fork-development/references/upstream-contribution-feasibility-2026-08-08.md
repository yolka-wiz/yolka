# Upstream contribution feasibility — RTL PR back to PDF4QT (2026-08-08)

Research session: can albdf's RTL work be contributed to upstream PDF4QT without risking
`yolka-wiz/al-bdf-engine`? Verdict: **yes — via a fresh MIT fork + staged PRs**; never PR
from al-bdf-engine itself. All facts below verified live via `gh api` / repo contents.

## Upstream facts

| Item | Value |
|---|---|
| Repo | `JakubMelka/PDF4QT` (`Jacques/PDF4QT` is a 404 — don't use it) |
| Default branch | `master` |
| License | MIT — **relicensed from LGPLv3 on 2025-04-27** (README §2) |
| CLA | None required (README §5: "contributions can be freely submitted without the need to sign a CLA") |
| Contributing docs | No CONTRIBUTING.md, no PR/issue templates; root `AGENTS.md` = Codex instructions (preserve CRLF, don't run builds unless asked) |
| CI | `.github/workflows/ci.yml` triggers ONLY on push-to-master + workflow_dispatch — **PRs get zero CI checks** |
| Activity | Sole maintainer, active (pushed 2026-08-06), responds to issues same-day, works via direct `Issue #NNN` commits |
| PR history | Rare but merged: nyalldawson ×4 (Jan 2024, merged within days), raffaelemancuso ×3 (2023). All small fixes. 42 open issues |
| Existing RTL | **Zero** bidi/Arabic/Persian code in core; vcpkg.json = 9 minimal deps (tbb, openssl, lcms, zlib, openjpeg, freetype, libjpeg-turbo, libpng, blend2d) — **no harfbuzz/fribidi** |
| .gitattributes | `* text=auto eol=crlf` → blobs store LF; LF new files are fine for a PR |

## Fork divergence measurements (commands that worked)

```bash
cd /home/agent/workspace/al-bdf-engine
git fetch upstream --tags
git merge-base upstream/master HEAD                          # fork point
git rev-list --count $(git merge-base upstream/master HEAD)..HEAD   # 153 ahead
git rev-list --count HEAD..upstream/master                        # 1,414 behind
git diff --name-status upstream/master..HEAD | awk '{...}'        # 153 A / 6 M / 331 D / 794 R
git diff --name-status upstream/master..HEAD | awk '$1=="M" {print $2}'  # the only files really modified
```

Key interpretation: the tree move to `src/` shows as ~794 renames; only **6 files** are
genuinely modified, of which exactly **one is core-relevant**: `pdftextlayoutgenerator.cpp`.

## The RTL patch surface (what an upstream PR would actually contain)

| Piece | Files | Size | Notes |
|---|---|---|---|
| RTL shaping + Type0 font engine | `pdfrtltextengine.{h,cpp}` | +835 lines | New; FriBidi + HarfBuzz + FreeType |
| Text normalizer | `pdfrtltextnormalizer.{h,cpp}` | +378 lines | New; logical↔visual, ligatures, lam-alef |
| /ActualText marked-content capture | `pdftextlayoutgenerator.cpp` | **+~60 real lines** | 2 new includes + `performMarkedContentBegin/End` overrides; the "136/80" stat is CRLF+header noise |
| Build | `Pdf4QtLibCore/CMakeLists.txt` | +4 lines | (fork registers the files at lines 167-170) |
| Deps | `vcpkg.json` | +2 (harfbuzz, fribidi) | The contentious item — upstream is deliberately 9-dep minimal |
| Tests/fonts | fixtures + 1 test | small | Fonts already OFL (Noto Naskh Arabic, Noto Sans Hebrew, Vazirmatn) — clean for MIT |

## License mechanics (the one hard problem)

- albdf's new code = **GPL-3.0-or-later** (ADR-0005, 2026-08-04). Upstream = **MIT**.
- GPL code cannot be merged into an MIT repo. BUT the user is the sole copyright holder
  ("albdf contributors" = user + agent work under their direction), so:
  **dual-license the RTL files — MIT-headed copies in the PR branch, GPL stays in albdf.**
- Hygiene: never let a GPL header ride into a PR (modified MIT file + GPL header = license
  mess the maintainer should reject). Verify authorship of every line first.
- ADR-0005 exists precisely because MIT is GPLv3-compatible (albdf's own licensing is
  sound); the relicense direction here is the reverse and requires the copyright holder.

## Recommended strategy (protects the main repo)

1. **Create `yolka-wiz/pdf4qt-rtl`** — fresh fork of `JakubMelka/PDF4QT`, MIT. Doubles as
   the patch home (published immediately, survives upstream rejection) and the PR vehicle
   (GitHub fork relationship recognized).
2. **Re-express the patch onto fresh master**: 4 new files with MIT headers + the
   layoutgenerator delta + CMake/vcpkg hunks. Build + run RTL tests locally (no CI on PRs).
3. **Split the contribution**:
   - PR #1: /ActualText marked-content capture in `PDFTextLayoutGenerator` + test
     (~60 lines, high odds, matches his own 2026-07-12 "Text editing update" work).
   - PR #2: `PDFRTLTextEngine` + `PDFRTLTextNormalizer` + vcpkg deps + tests, with a
     design note on why FriBidi/HarfBuzz vs Qt-native `QTextLayout` (Qt bundles HarfBuzz;
     be ready to justify or make the deps optional).
   - PR #3 (only if #2 lands): GUI wiring (form-field/FreeText AP, RTL search adapter —
     designs already mapped in M13/M14 references).
4. If upstream says no → patches live in the MIT fork forever; zero loss.

Never: PR from al-bdf-engine (GPL headers + `src/` restructure + rename + 1,414-commit gap),
merge upstream into al-bdf-engine for this, or touch protected main.

## Measurement traps (learned this session)

1. **`git describe --tags <merge-base>` returns the FORK's own tag** (0.3.0) — the base is
   an ancestor of the fork tag, so describe is meaningless for the upstream base. Fetch
   upstream tags and compare against those instead.
2. **Blob-to-blob `git diff upstream/master:PATH src/PATH` is CRLF-noise-dominated** when
   one side stored CRLF: the fork stored CRLF, upstream stored LF → every line differs and
   stats like "136 insertions/80 deletions" are fiction. Use
   `git diff -w -B --ignore-space-at-eol` and read the real +/- lines.
3. **`git diff --name-status` has rename detection ON by default** → a tree move shows as
   R entries; the M list is the only trustworthy "what actually changed upstream" signal.
4. `gh api repos/Jacques/PDF4QT` 404s — correct owner is `JakubMelka`.
5. The `--stat` option must come BEFORE the blob paths in `git diff` (options-order fatal).

## Risk critique (condensed from the session's severity table)

| Sev | Risk | Mitigation |
|---|---|---|
| High | 1,414-commit drift → rebase conflicts (layoutgenerator changed 2026-07-12) | Rebase patch onto fresh master; reconcile manually; don't modernize the fork first |
| High | GPL→MIT relicense | Sole copyright holder; verify authorship; MIT heads on PR copies |
| Medium | New deps in a 9-dep project | Design note; optional/guarded; lead with rationale |
| Medium | 1,700-line PR vs ≤100-line merged history | Split into phases; PR #1 wins trust |
| Medium | No CI on PRs | Local green on current master is the only evidence; script it into the PR description |
| Low | CRLF/style | `.gitattributes` normalizes; keep `PDF*`/`pdf::` naming (already done) |
