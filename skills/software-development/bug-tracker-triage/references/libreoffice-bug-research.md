# LibreOffice tracker research notes

## Instance facts
- Bugzilla: bugs.documentfoundation.org — REST works read-only, no auth.
- Gerrit: gerrit.libreoffice.org — `bug:` operator returns 0 results; use `message:"tdf#<id>"` (quoted). Changes live in project `core`, branch `master`.
- Commits land in git.libreoffice.org/core; daily builds at dev-builds.libreoffice.org. A bugzilla comment from `libreoffice-commits` includes the commit hash + change number.
- Shallow clones may not contain recent fix commits (`git show <hash>` comes back empty) — use Gerrit/gitiles for patch archaeology, but all target source files usually exist locally.

## Bugzilla component → top-level repo module (in a LibreOffice core checkout)
- Writer → `sw/` — find/replace: `sw/source/core/crsr/findattr.cxx` + `findtxt.cxx` (lcl_CleanStr); comment-print format: `sw/source/core/doc/doc.cxx` (`lcl_FormatPostIt`); layout/paint: `sw/source/core/layout/` (paintfrm.cxx, layact.cxx).
- Calc → `sc/` · Impress/Draw → `sd/` + `svx/` (basic/flowchart shapes in `svx/source/customshapes/`, e.g. EnhancedCustomShapeGeometry.cxx / TypeNames.cxx).
- Chart → `chart2/` · UI → `cui/`, `fpicker/`, `*/uiconfig/*.ui` · filters → `filter/`, `oox/`.
- Autocorrect ENGINE → `editeng/source/misc/svxacorr.cxx` (not sw/) — Writer UI sits on top.
- Dictionaries/data → `extras/source/wordbook/technical.dic`.
- Component "LibreOffice" (generic) = cross-cutting cleanup topics (include removal, integer-type conversion) — usually S/M per-batch patches.
- easyHack keyword = official newcomer marker; `whiteboard` carries `target:X.Y.Z` (legacy noise) and `reviewed:YYYY` (useful). Keywords like `difficultyBeginner`, `skillCpp`, `topicCleanup` refine it.
- Severity is not size: easyHack enhancements can be smaller than normal-severity bugs.

## Worked example — 2026-08-09 research pass (all IDs verified live)
Ranked candidates "small, open, with progress":
1. tdf#87605 "update technical dictionary" — data file only; merged patch 4 days prior (Add DevOps/cloud terms); S; `extras/`.
2. tdf#119931 "Fix accessibility warnings in .ui files" — XML only; active series (chart2/sc/sw merged, 2026); an ABANDONED fpicker/uiconfig patch is a direct pick-up point; S.
3. tdf#82579 "get rid of premac.h/postmac.h wrapper headers" — mechanical include removal, 2 merged patches in 2026; S/M; needs compile-verify only.
4. tdf#90152 "Formatting of printed comments is hard to read" — single fn `lcl_FormatPostIt` in `sw/source/core/doc/doc.cxx`; dev (aaron) analyzed fix 2026-03-31; S; MUST be locale-aware (French wants space before colon — naive English fix rejected).
5. tdf#105822 "Magnetic disk / Direct access storage / Direct data shapes' rendering" — merged fix 2026-06-29 covers only one shape; follow-up = sibling shapes in svx/customshapes; ASSIGNED to buzea.bogdan (likely taken — verify first).
6. tdf#35055 "background image covers paragraph shadow" — dev (buzea.bogdan) reproduced on 26.2.2.2, 2026-05-31; sw/layout painting; M.
7. tdf#35515 "Autocorrect capitalizes dotted email addresses" — trigger: first part ≥3 chars; code at editeng/source/misc/svxacorr.cxx ~L906; S/M; weak recent dev signal (QA nudge only).
8. tdf#35304 "3D transparency background foreground confusion" (Chart) — retested still broken 2026-07-17; chart2/; M; visual-only verification is the hard part.

Avoid-list rationale:
- tdf#55960 (Calc fill incremental numbers) — 6 ABANDONED Gerrit attempts (canonicalize floating-point); real bug, naive approach keeps failing review.
- tdf#35250 (Writer S/R back-references) — maintainer jluth: "Not at all trivial… I don't intend to attempt this"; needs utl::TextSearch API extension.
- tdf#32747 (duplicated LibreOffice in Windows Open-with) — Windows-only testing.
- Bugs whose only recent comment is a qa-admin retest nudge (e.g. tdf#34749, tdf#33838) — no real progress.
