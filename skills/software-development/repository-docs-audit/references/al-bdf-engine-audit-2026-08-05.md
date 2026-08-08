# al-bdf-engine docs audit — 2026-08-05

Worked example of `repository-docs-audit` on `git@github.com:yolka-wiz/al-bdf-engine.git`
(pdfedit: headless PDF editing library + CLI, fork of PDF4QT, GPL-3.0-or-later).

## Commands that surfaced the findings

```bash
# orient
git fetch && git status -sb && git log --oneline -15 && git tag -l

# man page vs README command coverage (both real outputs)
grep -o '\\fB[a-z-]*\\fR' docs/PdfTool.1 | sort -u
# → delete-object fetch-text html recognize-text xml ...  (only 4 real commands)

grep -o 'PdfTool [a-z-]*' README.md | sort -u
# → add-text delete-object form-fill form-list help recognize-text
#   search-text sign verify-signatures

# tracking DB reconstruction (DB is gitignored; schema+seed committed)
python3 scripts/db.py init && python3 db/seed.py
python3 scripts/db.py status
# → ALL 9 components "planned", ALL 13 tasks "open", ADRs "proposed"
#   while README claims "M0–M8 complete" → seed never updated post-0.1.0

# ADR numbering drift
ls docs/decisions/        # 0001..0006 exist
# docs/AGENT.md still said "next free number is 0005"

# repo visibility (200 unauth = PUBLIC)
curl -s https://api.github.com/repos/yolka-wiz/al-bdf-engine | jq .private
# → false

# live API key committed in a public repo
grep -rn "ctx7sk-\|Bearer ctx7" docs/          # docs/setup-context7.md
```

## Severity table delivered

| Sev | Doc | Finding |
|---|---|---|
| HIGH | docs/PdfTool.1 | Missing shipped commands: add-text, search-text, form-list, form-fill, sign, verify-signatures. Header still 2026-08-04/0.1.0. |
| HIGH | db/seed.py | Fresh clone + init + seed reports everything planned/open/proposed — contradicts README/PLAN. `db.py dump` not committed. |
| HIGH | docs/setup-context7.md | Live context7 API key in a PUBLIC repo — rotate, don't just redact. |
| MED | docs/AGENT.md | ADR numbering refs stale (0001–0004 / "next is 0005" — actual 0006). |
| MED | plans/PLAN.md | M3 checkboxes unchecked though shipped; ADR table missing 0005/0006; open questions answered long ago. |
| MED | docs/RELEASES.md | Only 0.1.0; M8 forms/signatures, M8.1 sweep, GPL relicense, search fixes unreleased-note'd. |
| LOW | README.md | "PLAN (M0–M7)" → M0–M8.1; references deleted `tools/` dir; test counts say 10 → 11. |
| LOW | docs/PROBLEMS.md | "Planned (post-M7)" items 1–2 (Forms, Signatures) already done; D#2 tools/ deleted. |

## What was HEALTHY (also worth noting)

- PROBLEMS.md was current: P1–P5 with fix shas, R#1–3, S#1–2, compat-sweep section.
- ADR-0005/0006 files themselves were accepted and well-formed; only cross-references stale.
- Git identity consistent: `Yolka <yolka@pdfedit.local>` per PROBLEMS.md.
- Context7 vendored docs (docs/context7/) matched their README metadata (fetched 2026-08-04).

## Follow-ups offered to user

Man page commands, seed.py/DB sync, PLAN+README+RELEASES updates, key rotation.
