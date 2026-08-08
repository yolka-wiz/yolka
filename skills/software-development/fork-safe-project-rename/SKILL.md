---
name: fork-safe-project-rename
description: "Rename fork binary/project; keep cherry-picks working."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rename, refactor, fork, cmake, rebrand, cherry-pick]
    related_skills: [git-secret-purge, github-repo-management]
---

# Fork-Safe Project Rename

Renaming a project (product name, CLI binary, CMake project, DB file) inside a
fork of an upstream repo. The hard part is renaming the USER-FACING names
while leaving UPSTREAM-INTERNAL names untouched so future upstream
cherry-picks still apply.

## When to Use

- User says "rename the program to X" / "rename the project/binary".
- Rebranding a fork's CLI while keeping the upstream base intact.

## Core Principle

| Rename | Keep |
|---|---|
| Product/project name (`pdfedit` → `albdf`) | Upstream library name (`Pdf4QtLibCore`) |
| CLI binary (`PdfTool` → `albdf`) | Upstream class names (`PDFTool*`, `PDF*`) |
| CMake `project()` / version macros | Upstream dir layout (`src/PdfTool/`) |
| Man page, README, docs, license headers | Source filenames (`pdftooladdtext.cpp`) |
| DB file, vcpkg manifest name | Upstream baseline/research docs (they document upstream behavior) |

Rationale: renaming vendored upstream dirs/classes/files breaks `git diff`
against the fork base and destroys cherry-pick diffs. Only user-facing names
change.

## Workflow

1. **Inventory first.** `git grep -l -E "oldname|OldBinary"` to get every file.
   Classify each match: project name vs binary vs class vs filename substring.
2. **Word-boundary regex with a caveat.** `re.sub(r"\boldname\b", "newname", s)`
   protects substrings like `pdfeditorfallbackfont` (a filename) — but `_` is a
   WORD character, so `\bpdfedit\b` does NOT match `pdfedit_signature_%1`.
   After the regex pass, grep for `oldname[a-z_]*` to catch runtime strings
   embedded in identifiers.
3. **Fix the ones the regex missed by hand:**
   - `add_subdirectory(PdfTool)` must stay the dir name while the CMake target
     inside is renamed (`add_executable(albdf ...)`).
   - `.TH PDFTOOL 1` in the man page is uppercase — regex on `PdfTool` misses it.
   - Include guards (`PDFTOOLABSTRACTAPPLICATION_H`) stay — upstream.
4. **Move the man page** with `git mv`, then update `.TH` + references.
5. **Update gitignore for renamed artifacts.** If `db/pdfedit.db` → `db/albdf.db`,
   the OLD name is no longer ignored — a stale file can slip into a commit.
   `git rm --cached` it.
6. **Update license/copyright headers** in authored files only (`pdfedit
   contributors` → `albdf contributors`); never touch vendored MIT headers.
7. **Runtime strings** (signature field names, application names) — grep
   `setApplicationName`, `QStringLiteral("old*")` etc.
8. **If history was rewritten too** (e.g. secret purge earlier), remap ALL
   old shas referenced in docs by subject via `git log --oneline --reverse`.

## Pitfalls

1. **`_` is a word char** — `\bpdfedit\b` silently misses `pdfedit_signature_1`.
   Follow every word-boundary pass with `oldname[a-z_]*` grep.
2. **Line endings.** A text-mode script on CRLF files (vendored upstream)
   rewrites every line → 34-line diff for a 1-line change. Use byte-level
   replace (`open(p,'rb')`, `.replace(b"old",b"new")`) to keep diffs clean.
3. **Don't rename what upstream will overwrite.** Dir layout, class names,
   include guards, file names — keep them or cherry-picks break.
4. **Docs reference old shas.** After ANY history rewrite, `git rev-parse
   --short 0.1.0` and remap doc shas; old shas are all MISSING.
5. **Stale gitignore after DB/artifact rename** — verify with
   `git status --short` after `git add -A`; a renamed-but-unignored artifact
   will appear and must be `git rm --cached` + committed separately.
6. **Two commits, not one:** rename commit + any follow-up cleanup commit
   (removing accidentally committed artifacts). Keeps the diff reviewable.

## Verification Checklist

- `git grep -i "oldname"` → only historical/upstream references remain
- `git grep "oldbinary "` (CLI invocation) → empty
- Man page renders: `groff -man -Tutf8 docs/newname.1`
- `git status --short` clean after `git add -A`
- C++ build if toolchain available; else static grep + note the gap

## References

- Session example (2026-08-05): `pdfedit`/`PdfTool` → `albdf` in
  yolka-wiz/al-bdf-engine (68 files) — word-boundary regex + 8 hand fixes,
  git mv of man page, byte-preserving vcpkg.json edit, stale DB gitignore fix.
