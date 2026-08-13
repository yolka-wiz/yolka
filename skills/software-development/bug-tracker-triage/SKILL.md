---
name: bug-tracker-triage
description: Find small fixable upstream bugs via Bugzilla/Gerrit triage.
---

# Bug Tracker Triage (Bugzilla + Gerrit)

Find small, currently-open upstream bugs that are realistically fixable by a single contributor and show signs of PROGRESS (recent real activity, assignee, or patches in the review system). Read-only research — do NOT fix anything.

## When to use
- "Find 5-8 small easy bugs to fix in project X"
- "Which open bugs have open patches / recent dev activity?"
- Any research pass over bugs.documentfoundation.org, other Bugzilla REST instances, or Gerrit code review.

## Workflow
1. **Candidate queries (Bugzilla REST)** — always REPEAT multi-value params; comma lists are silently ignored (see Pitfalls).
   - Easy bugs: `curl -sL "https://bugs.documentfoundation.org/rest/bug?product=LibreOffice&bug_status=NEW&bug_status=UNCONFIRMED&bug_status=REOPENED&keywords=easyHack&include_fields=id,summary,component,severity,status,resolution,last_change_time,assigned_to,whiteboard&limit=100"`
   - Recent small bugs: same base + `&severity=normal&severity=minor&severity=trivial&order=last_change_time%20DESC`
   - easyHack-style keywords are the project's official newcomer marker — prioritize them.
2. **Per-bug details** — comments do NOT come via `include_fields=comments`; use the dedicated endpoint:
   - `curl -sL "https://bugs.documentfoundation.org/rest/bug/<ID>/comment"` → `{"bugs": {"<id>": {"comments": [...]}}}`
   - First comment (repro) + last comment (author/date/text) usually suffice. The LAST comment's author decides whether recent activity is real or automated.
3. **Gerrit progress check per bug**:
   - `curl -sL "https://gerrit.libreoffice.org/changes/?q=message:%22tdf%3CID%3E%22&n=6"` — quoted `message:"tdf#<ID>"` is the reliable operator (`q=bug:<ID>` often returns 0).
   - Strip the `)]}'\n` prefix before JSON parsing.
   - Classify: MERGED = workstream alive (recent merged = strong signal); NEW = someone mid-fix (bug likely taken); ABANDONED = pick-up opportunity OR a naive approach that failed review — read the change to tell which.
4. **Analyze progress honestly**:
   - Real signals: `libreoffice-commits` comments ("committed a patch… pushed to master"), maintainer/developer comments, assignee set, recent merged Gerrit changes.
   - Fake signal: `qa-admin` "Dear <reporter>, please retest this bug…" nudges — they bump `last_change_time` but mean NO progress. Bugs whose only recent comment is a qa-admin nudge must be treated as inactive.
5. **Verify scope against the local checkout** — grep comments for function names/strings to pin the exact file (e.g. `grep -rn lcl_FormatPostIt /path/sw`). If the fix is data/XML-only (dictionaries, .ui files, help text) it's an S-size win with NO C++ build. Confirm the repo exists before assuming paths.
6. **Rank**: smallest + most progress + clearest repro first. Size S = data/XML or single function, no API change; M = one focused function, compile-verify only; M+ = API/state-machine changes — flag it and drop unless nothing better. State uncertainty honestly (no-progress bugs say so).

## Pitfalls
- **Comma-separated multi-value params are silently ignored by Bugzilla REST.** `bug_status=NEW,REOPENED` returns wrong result sets; `severity=normal,minor,trivial` returns 0 bugs. Repeat the param: `&bug_status=NEW&bug_status=REOPENED`. First symptom: filters "not applied" or empty results.
- **`include_fields=comments` does not return comments** in `/rest/bug` — use `/rest/bug/<ID>/comment`.
- **Gerrit `o=SUBJECT` is invalid** ("SUBJECT is not a valid value for -o"); subject is returned by default — don't pass it.
- **Gerrit `bug:<id>` can return 0 results even for bugs with commits** (observed on LibreOffice's instance). `message:"tdf#<id>"` (quoted) is the reliable operator; unquoted/bare number search matches change numbers, not bug refs.
- **Automated QA nudges inflate last_change_time** — always check the last comment's author before believing "recent activity".
- **Assigned bugs are often taken** — an assignee or a just-merged fix means someone owns the work; the bug may still list a next sub-task (e.g. sibling shapes after a partial fix), but verify no patch is in flight before starting.
- **Many ABANDONED Gerrit changes = trap**: the bug is real but the obvious approach keeps failing review (e.g. floating-point canonicalization attempts). Don't re-attempt the abandoned approach without a new idea.
- **Maintainers state difficulty in comments** — quotes like "Not at all trivial to accomplish this. I don't intend to attempt this" are authoritative size-M+ verdicts. Respect them.

## Reference
- `references/libreoffice-bug-research.md` — LibreOffice-specific tracker facts (component→module map, easyHack/whiteboard conventions) and a worked, ranked example list from a 2026-08 research pass.
