# Secret purge + project rename — al-bdf-engine, 2026-08-05

Worked remediation for the `repository-docs-audit` findings on
`git@github.com:yolka-wiz/al-bdf-engine.git`. Full sequence: audit → purge
committed API key from history → rename project/CLI `pdfedit`/`PdfTool` →
`albdf` → fix stale docs → verify.

## 1. Purge the secret from ALL history (git-filter-repo)

```bash
# install (into a venv; PEP 668 systems need --python <venv>/bin/python)
uv pip install --python ~/workspace/agent-env/bin/python git-filter-repo

# mapping file: one 'old==>new' per line
cat > /tmp/ctx7-key-replace.txt <<'EOF'
ctx7sk-2c7fa156-7263-4e9a-95ac-ef0417f28179==>***REDACTED: CONTEXT7_API_KEY***
EOF

# run from repo root
~/workspace/agent-env/bin/git-filter-repo --replace-text /tmp/ctx7-key-replace.txt --force
#   - Aborts without --force if the clone isn't "fresh" (any untracked/ignored
#     file, e.g. a db/*.db created during the audit, triggers the refusal).
#   - Removes the 'origin' remote as a safety move — re-add it before pushing.
#   - Rewrites EVERY commit sha (even unrelated commits). Tags are preserved
#     but their shas change too.

git remote add origin git@github.com:yolka-wiz/al-bdf-engine.git
git push --force origin main
#   - --force-with-lease fails with "stale info" right after a history rewrite;
#     run `git fetch origin` first, then plain `--force` (already authorized).
```

Verify the key is unreachable:

```bash
git log --all --oneline -S "ctx7sk" | head        # empty = purged
git grep -l "ctx7sk" $(git rev-list --all)        # empty = clean
```

IMPORTANT: **rotation is the real fix, not the rewrite.** The repo was public
(`api.github.com` returned 200 unauthenticated), so the key was already
scrapable. History rewrite is containment; the user must rotate the key on the
provider side. Local runtime config (`hermes config set ...`) keeps working
until rotation.

## 2. Remap commit shas cited in docs

filter-repo changes every sha, so RELEASES / PLAN checkboxes / PROBLEMS fix
columns that cite short shas now point at dead hashes. Fix by subject-matching:

```bash
git log --oneline --reverse          # full rewritten history, oldest first
```

Build an old→new map by matching each subject line (e.g. "M3 add-text (LTR)"
→ its new sha), then replace across docs:

```python
remap = {"942d55a": "327061b", ...}   # old sha -> new sha by subject
for f in files:
    content = open(f).read()
    for old, new in remap.items():
        content = content.replace(old, new)
    ...
```

Then re-verify: `git log --all -S` for old shas should be empty.

## 3. Rename pitfalls (pdfedit/PdfTool → albdf)

- **Word-boundary regex misses underscore-joined runtime strings.**
  `re.sub(r"\bpdfedit\b", "albdf", ...)` did NOT catch
  `QStringLiteral("pdfedit_signature_%1")` in `pdftoolsign.cpp` — `_` is a
  word char, so `\b` doesn't fire. After a global rename, grep for
  `name[a-z_]*` to find stragglers. This string is user-visible (the signature
  field name written into PDFs), so it matters.
- **Vendored upstream files: restore and redo byte-preserving.**
  A text-level replace script normalizes CRLF → LF in vendored files (e.g.
  `src/README.upstream.md`, `src/vcpkg.json`), turning a 1-line change into a
  200-line diff and polluting the commit. Fix: `git checkout -- <file>`, then
  do a byte-preserving replace:
  ```python
  data = open(p, "rb").read()
  open(p, "wb").write(data.replace(b"pdfedit", b"albdf"))
  ```
  Keep upstream naming for fork hygiene: dirs (`src/PdfTool/`), class names
  (`PDFTool*`, `pdftool*` files), library (`Pdf4QtLibCore`) stay; only the
  user-facing binary/project/man page/macros change.
- **`.gitignore` drift after rename.** After `db/pdfedit.db` → `db/albdf.db`
  in `.gitignore`, the OLD name is no longer ignored, so a stale
  `db/pdfedit.db` created during the audit got committed accidentally. Check
  `git status` for the old artifact name; `git rm --cached` it.
- **CMake `add_subdirectory` vs target name.** `add_subdirectory(PdfTool)`
  keeps the DIRECTORY name even when the executable target inside is renamed:
  `add_executable(albdf ...)`. The sed must not rename the subdirectory call.
- **`git mv` then edit:** stage the rename, then edit content — edits after
  `git mv` remain unstaged. Verify with `git show HEAD:<file>` vs working tree.

## 4. Docs that needed content fixes (beyond the rename)

- Man page missing M8 commands (`form-list`, `form-fill`, `sign`,
  `verify-signatures`) — added `.SS` sections; header `.TH ALBDF 1` +
  current date/version. Renders with `groff -man -Tutf8 docs/albdf.1`.
- `db/seed.py` rewritten to CURRENT state: components `done`, tasks closed with
  `evidence_ref` shas (schema supports `evidence_ref`), ADRs accepted/
  superseded, questions answered — so a fresh clone reconstructs truth.
- PLAN M3 checkboxes ticked, ADR table 0001–0006 with real statuses, open
  questions → answered; docs/AGENT.md ADR numbering → next free 0007;
  RELEASES gets a post-0.1.0 entry; PROBLEMS planned-items → shipped;
  README test counts 10→11, PLAN M0–M8.1, removed dead `tools/` line.

## 5. Verification checklist

- `git log --all -S "<secret>"` → empty; remote sha == local sha
  (`git ls-remote origin main` vs `git rev-parse HEAD`)
- `git status` clean (no accidentally-committed DB/artifact)
- man page renders: `groff -man -Tutf8 docs/albdf.1 | head`
- DB truth: `db.py init && seed.py && db.py status` matches README/PLAN claims
- No `PdfTool`/`pdfedit` stragglers except intentional upstream references
  (class names, vendored docs, baseline research notes)

## Caveat: no C++ build possible in the audit container

Qt/vcpkg toolchain absent (ephemeral container). Rename verified by grep, man
page render, DB seed — NOT by a compile. Flag this honestly; the dev container
must run `ci/run-ci.sh` before the next release.
