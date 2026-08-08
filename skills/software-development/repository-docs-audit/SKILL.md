---
name: repository-docs-audit
description: "Audit repo docs for staleness and consistency."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [docs, audit, staleness, repo-health, ADR, man-page, tracking-db]
    related_skills: [github-repo-management, codebase-inspection]
---

# Repository Documentation Audit

Systematic staleness check of a repo's documentation and status claims.
Use when the user asks to "check the repo", "see if the docs are updated",
"look around and see if everything is fine", or before trusting a repo's
README/plan as ground truth for further work.

## When to Use

- "check `<repo>`, see if the docs are updated and everything is fine"
- Starting a contribution session on an unfamiliar or long-idle repo
- Before relying on README status, milestone plans, or a tracking DB
- After a milestone merge, to confirm docs were actually updated
- "Index the repo so future AIs can read/build faster" — build a
  deterministic REPO_MAP.md generator + pre-commit hook + CONTRIBUTING rules
  (recipe: `references/repo-indexing-and-hooks.md`)

## When the user asks "what's left to add" (roadmap)

Answer from the repo's OWN tracking docs — never from memory or invention:

1. `python3 scripts/db.py tasks --open` and `questions --open` (if a tracking
   DB exists). Empty there does NOT mean nothing left — closed DB + live
   project means the roadmap moved into PLAN/PROBLEMS prose.
2. Read `plans/PLAN.md` future milestones + `docs/PROBLEMS.md` "Planned /
   future / backlog / design debts" sections.
3. **Known-limitation tables are feature candidates.** PROBLEMS.md P1–P5 /
   R#1–R#3 / S#1–S#2 style entries = the product's sharp edges; for a
   differentiated project (RTL, search) these are usually higher-value than
   the explicitly "Planned" list.
4. Categorize the answer: **features** (from PLAN/PROBLEMS planned),
   **differentiator debt** (known limitations that are the product moat),
   **quality backlog** (perf benchmarks, hosted CI, docs flows), and
   **housekeeping** (security rotation, CI gates, collaboration notices).
   Label each with effort S/M/L and which are user actions vs agent actions.
5. Present as a table and recommend a priority; then offer to start the top
   item (with a failing test first, per the repo's TDD rule).
6. If the top differentiator-debt item is a **search/extraction limitation**
   (single-item matching, ligature degradation, cross-item spans), the audit
   should ALSO produce a verified red repro before the follow-up plan — the
   field flake (e.g. dense-page item split) is rarely reproducible on demand,
   so force the split deterministically (two adjacent `add-text` runs → 2
   items → phrase query = 0, confirm with `recognize-text`). Recipe + design
   for this exact pattern: `references/s1-cross-item-search-2026-08-05.md`.

## Method

1. **Orient** — `git fetch && git status -sb`, `git log --oneline -15`,
   `git tag -l`, `git remote -v`. If docs commits trail feature commits,
   expect drift.
2. **Read the ground-truth docs** — README.md, `plans/PLAN.md`,
   `docs/RELEASES.md`, `AGENTS.md`, `docs/AGENT.md` (the docs guide). Note the
   version/date each claims.
3. **Cross-check status claims**:
   - README status line vs PLAN milestone checkboxes vs RELEASES entries.
   - PLAN `[x]` boxes vs the commit shas cited vs README claims.
   - ADR numbering: docs often say "next free number is N" — verify against
     the actual highest file: `ls docs/decisions/`. Stale by multiple ADRs is
     common.
   - Man page header (`.TH ... "date" "version"`) vs latest release/tag.
4. **Command-docs coverage** — CLI-first projects: diff man-page commands vs
   README commands. Every shipped command missing from the man page is a HIGH
   finding (the man page is almost always the LAST doc updated):
   ```bash
   grep -o '\\fB[a-z-]*\\fR' docs/*.1 | sort -u
   grep -o 'PdfTool [a-z-]*' README.md | sort -u   # adjust binary name
   ```
5. **Tracking DB reconstruction** — if the DB file is gitignored (schema +
   seed committed instead), rebuild it to see what a fresh clone gets:
   `python3 scripts/db.py init && python3 db/seed.py` (adjust to repo's CLI),
   then compare with README/PLAN claims. A seed reporting everything
   "planned/open/proposed" while README says milestones complete = HIGH.
6. **Security scan** — repo visibility: `curl -s https://api.github.com/repos/<o>/<r>`
   (200 unauthenticated ⇒ **public**). Grep committed files for key patterns:
   `sk-`, `ctx7sk-`, `AKIA`, `token=`, `Bearer `. A live API key in a public
   repo is HIGH: recommend **rotation** (it's already exposed on GitHub) plus
   removal, and note where the runtime config should hold it instead.
7. **Report as a severity table** — one HIGH/MED/LOW row per stale artifact,
   each with the concrete mismatch and the fix. Then offer to fix in small
   conventional commits. (User preference: findings in severity-table format,
   reviewed through an engineer's lens — SPOFs, drift, security.)

## Pitfalls

- **Gitignored tracking DB**: the DB can be the declared "source of truth"
  yet never committed — only `schema.sql` + `seed.py` are. Fresh clones rebuild
  to the seed's (often initial) state, so a rebuilt DB never reflects current
  status. Check whether `db.py dump` output is committed; if not, flag it.
- **ADR references go stale**: "next free number is 0005" stays stale for
  commits after 0006 lands. Always verify against `ls docs/decisions/`.
- **Deleted dirs linger in layout docs**: README/PLAN still reference scaffold
  dirs (`tools/`) that were removed. `ls -d` every dir listed in a layout block.
- **Man page ≠ README**: command lists drift fastest; diff them explicitly.
- **Test counts drift**: README hardcodes "10 tests" while the suite grew to
  11. Verify against the test CMake/unit-test files, not the prose.
- **Public-repo secrets**: unauthenticated `api.github.com` returning 200 means
  public — any key in the tree is already scrapable. Rotate, don't just redact.

## Worked example

`references/al-bdf-engine-audit-2026-08-05.md` — full audit of the
al-bdf-engine (pdfedit) repo: exact commands, findings, severity table.

`references/s1-cross-item-search-2026-08-05.md` — verified red repro +
root cause + design for a search limitation turned into a TDD plan
(cross-item RTL search, PROBLEMS.md S#1).

`references/repo-indexing-and-hooks.md` — building REPO_MAP.md (deterministic
generator), a pre-commit hook that regenerates it, a markdown structure gate,
and CONTRIBUTING rules, so future agents read/build faster.
