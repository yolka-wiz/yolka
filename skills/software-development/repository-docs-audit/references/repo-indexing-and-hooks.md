# Repo indexing for future AI agents — REPO_MAP + pre-commit hook

Pattern from albdf (2026-08-05): user asked to "index the repo so future
AIs could read and build faster". Deliverables: deterministic `REPO_MAP.md`
generator, a pre-commit hook that regenerates it, and CONTRIBUTING rules.

## When to use

- User asks to "index the repo", "make it easy for future AIs to read/build",
  or wants the repo self-orienting for agents.
- Any repo where onboarding means reading 10+ docs before the first build.

## Deliverables (what was built, in order)

1. `scripts/gen-repo-map.py` — deterministic REPO_MAP.md generator.
2. `.githooks/pre-commit` — regenerates + stages REPO_MAP.md; runs the
   markdown structure gate on staged .md files.
3. `scripts/install-hooks.sh` — `git config core.hooksPath .githooks` +
   chmod +x the hook (per-clone; commit the hook file itself so every clone
   can install the same hooks).
4. `scripts/check-markdown-structure.py` — doc structure gate.
5. `CONTRIBUTING.md` — five binding contribution rules (below).
6. Point new agents at the map: `AGENTS.md` §quick-map mentions REPO_MAP.md +
   CONTRIBUTING.md first; README lists the new scripts.

## REPO_MAP.md generator — the determinism rules

The repo's determinism law applies to generated files: **no timestamps, no
absolute paths, sorted output**. Verify by running the generator twice and
comparing sha256 — identical output required.

Sections that worked well (all computed from the tree, hand-curated where
automation can't know intent):

- Header: purpose + pointer to the binding contract (AGENTS.md / DB).
- Quick start: build + test commands (CMake/vcpkg/ctest/smoke) — the #1 thing
  a future agent needs.
- Top-level directory map: hand-curated one-line purpose per dir, auto-checked
  against the live tree (flag missing/unmapped dirs).
- Document index: every markdown file except README.md, with title + one-liner
  extracted from the first heading + first paragraph (trim ~180 chars).
- Key source files: hand-curated role per file, existence-checked.
- DB status: only if the tracking DB exists (it's often gitignored — then
  print the rebuild command instead).
- Rules summary: pointer to CONTRIBUTING.md.

## Pre-commit hook design

- Regenerate + `git add REPO_MAP.md` so the committed map always reflects the
  committed tree. If regeneration fails: warn, do NOT block the commit.
- Run the markdown gate on **staged** .md files only
  (`git diff --cached --name-only --diff-filter=ACM -- '*.md'`), not the whole
  repo — fast, and only gates what you're about to commit.
- Gate failures abort the commit (exit 1) with a clear message + `--no-verify`
  escape hatch.
- `.githooks/` (committed) + `core.hooksPath` (per-clone config) is cleaner
  than copying into `.git/hooks/`.

## Markdown structure gate rules

User's rule: markdown files (except README.md) should be **structured, not
minimal** — logical, with sections. Mechanical checks that encode it:

- Must have an H1 title.
- ≥ 2 headings total (title + at least one section).
- Body floor (non-heading, non-fence lines): ~12, relaxed to ~8 for ADRs
  (`docs/decisions/000N-*` are deliberately terse).
- Balanced ``` fences.
- Exempt: README.md (the entry point), vendored/third-party dirs
  (`skills/`) — same cherry-pick-hygiene logic as the CI format gate's
  upstream exclusions.

Real-world catch: `docs/setup-context7.md` failed (single heading) and was
restructured; a vendored SKILL.md failed (no H1) and is exempt by the
vendored rule. Before setting thresholds, run the gate against the whole
existing corpus and tune exemptions/floors so it passes today's docs.

## CONTRIBUTING.md — the five rules (user-specified)

1. Create a branch, commit each major step.
2. Update docs about what you change, in the process.
3. Don't push to main until fully tested (CI gate green).
4. Update the problems doc your code change made (PROBLEMS.md: fixed/new).
5. Don't upload unnecessary files, secrets, or data to the repo.

## Verification checklist (do all before declaring done)

- Generator determinism: two runs → identical sha256.
- Positive hook test: commit a good doc → hook runs, REPO_MAP.md auto-staged.
- Negative hook test: commit a stub .md → gate FAILS, commit aborted,
  clear message.
- Ghost-entry pitfall: if the gate aborts AFTER the map was regenerated, the
  staged map may reference files that were later deleted — regenerate the map
  before the next commit.
- Secret scan: grep committed tree for `sk-`, `ghp_`, `AKIA`, `Bearer ` etc.
  (per repository-docs-audit security step).
- Full CI gate still green after adding the tooling.

## Files

`references/repo-indexing-and-hooks.md` (this note). The albdf implementation
commits: `ba374d4` (generator + hook + CONTRIBUTING), `300390c` (docs pointing
agents at the map).
