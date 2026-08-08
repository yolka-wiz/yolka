---
name: subagent-driven-development
description: "Orchestrate multi-phase implementation via subagents."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, orchestration, subagents, planning, gates, verification]
    related_skills: [plan, test-driven-development, systematic-debugging, coding-workflow]
---

# Subagent-Driven Development

Use when the user says "use subagents to develop the project" / "you are the
orchestrator", or when an implementation plan is too large/sequential for one
agent context. The orchestrator stays in control: it does recon, writes the
plan, dispatches one phase at a time, and closes the loop. Subagents do the
isolated work.

## Core principle

**The orchestrator never freewheels and never trusts self-reports.** Every
phase has a verifiable gate, and every child claim (commit sha, test result,
push) is verified by the orchestrator before the next phase starts.

## Workflow

1. **Recon first — what has ACTUALLY been done, not what docs claim.**
   - `git fetch origin --prune --tags` FIRST and read the output: a line like
     `+ old...new main -> origin/main (forced update)` means the remote
     history was rewritten (filter-repo scrub, rebase). `git pull` then
     refuses or diverges. Recover safely: (1) `git log --oneline
     origin/main..HEAD` to see local-only commits; (2) if they are
     pre-rewrite copies of remote commits, find the rewritten equivalent by
     commit message and confirm content-identity with `git diff --stat
     <local> <rewritten>` (empty = same tree, nothing unique lost); (3) only
     then `git reset --hard origin/main`. Also check for NEW branches and
     tags the fetch brought in.
   - `git log`/`git status`/branches: find real commits touching the area.
   - Check the project's tracking DB / issue tracker / PROBLEMS.md for the
     item's real state (open vs closed, evidence refs).
   - Verify the build baseline yourself: `ctest` green, working tree clean.
     **Then verify the baseline is FRESH, not just green.** A
     `build/bin/<binary>` older than the HEAD commit under test is a stale
     binary: ctest can report green against it while HEAD does not compile
     at all (real 2026-08-06 case: a wave-1 merge added QFlags values past
     bit 31; the pre-merge binary gave 11/11 green, and ALL three parallel
     children independently hit the compile break). Check
     `stat -c %y build/bin/<binary>` vs `git log -1 --format=%ci HEAD`;
     if the binary predates the commit (or a suspect feature commit), rebuild
     from clean FIRST. A false baseline poisons every child's first build.
   - A "plan exists" commit is NOT implementation — say so explicitly.
2. **Sync docs/DB to reality before dispatching.** Create the missing task
   entry, update the problems table with a pointer to the fix plan, commit
   the doc change as its own commit. Children then read accurate context.
   - **Reconcile doc-vs-DB drift first.** When docs claim tasks closed that
     have NO rows in the tracking DB (e.g. PLAN.md says "#21–#27 closed" but
     the tasks table stops at #20), re-create the rows and close them via the
     evidence-gated path (`task-add` + `task-done --ref <sha>`) using the
     commit refs already cited in the docs. Then add the next wave's tasks as
     `open` rows so children have a real queue to claim.
   - **Check task wording against reality before rescoping.** A task that
     says "wire upstream X" may already be done (command compiled, registered,
     responsive in the binary — verify with `binary cmd --help` and the
     static-registration pattern). If so, rewrite the task's real remaining
     work as verification + tests + evidence closure, and tell the child
     explicitly: "the wiring exists — your job is tests, not implementation."
     Stale plan wording is the trap; the binary is the oracle.
3. **Write the execution plan** (`plans/<slug>-execution.md` or the repo's
   plan convention): phases with files, exact commands, expected outputs,
   and a per-phase GATE (witnessed RED, full-suite green, extraction
   unchanged). Include ranked hypotheses for the risky part and a hard-stop
   rule (report after N failed fixes, never cargo-cult a workaround).
4. **Dispatch one phase per delegate** (or parallel batches only for
   independent work). Each child is a leaf with terminal+file toolsets.
   - **Decompose a milestone into PARALLEL WORKSTREAMS, not serial phases,
     when the user says \"implement with multiple subagents\".** Split the
     plan into: (1) a CRITICAL PATH workstream that everything else builds on
     (usually CMake/CI wiring, scaffolding, or a contract change) — dispatch
     FIRST; (2) INDEPENDENT analysis/audit/scaffold workstreams that don't
     need the critical path's output (dependency audit, fixture generation,
     static compile-risk pre-scan) — dispatch IN PARALLEL with it, each with
     its own goal/context so they don't wait on each other; (3) an
     INTEGRATION phase (full build + fix loop + gate) that runs only after
     the critical path lands and the parallel tracks report. Explicitly
     state in each child's context what IS and ISN'T its job (e.g. \"do NOT
     wire CMake — that's another workstream\") to prevent overlap on the same
     files. The delegation batch runs children in parallel automatically and
     returns one consolidated result; read the FULL per-task summaries (they
     arrive truncated — see footer paths) and verify each claim
     independently before starting integration. (Hit 2026-08-07: M12 GUI
     restore — WS1 CMake wiring as critical path, WS2 dependency/Qt-version
     audit + WS4 RTL fixture/smoke scaffold in parallel, WS5 integration
     build deferred until the other three reported.)
   - **Parallel batches need per-child filesystem isolation.** Multiple
     children in ONE checkout clobber each other (shared index, shared
     build dir, conflicting commits). Create a git worktree per child from
     the same base before dispatching:
     ```bash
     git worktree add -b m<ms>/<slug> /path/to/wt-<slug> origin/main
     # copy gitignored-but-needed state (tracking DB, configs) into each worktree:
     cp db/project.db /path/to/wt-<slug>/db/
     ```
     Write each child's execution plan into its own worktree and commit it
     as a docs commit on the branch, so the branch history carries the plan.
     Tell the child: "work ONLY in <worktree path>, never the main checkout."
     After dispatch, verify with `git worktree list` and check each branch
     separately before merging.
     **Worktree base trap:** `git worktree add -b <b> <path> origin/main`
     bases the branch on the REMOTE's state. If local main carries fixes the
     remote lacks (e.g. a build fix committed locally but not pushed), the
     worktree is broken at creation. Fix BEFORE dispatching: inside the
     worktree `git reset --hard main` (local branch), then re-copy any
     gitignored state (tracking DB). Verify the fix is present
     (`grep -c 'class Options' <file>` etc.) before the child starts.
   - Children know NOTHING of the conversation: pass repo path, binding
     AGENTS.md, build commands, offscreen env, TDD rules, commit convention
     (Conventional Commits, one logical change), and the report-back
     contract (exact numbers + sha, "never fabricate, stop and report
     instead of working around").
   - Paste the exact build/test commands and the phase's gate into the
     context — do not make the child guess. This includes correcting doc
     lies about the environment (e.g. AGENTS.md says vcpkg at /workspace/vcpkg
     but the machine has it at /home/agent/vcpkg-cache/vcpkg) — verify the
     real toolchain paths yourself in recon, then pin them in the context.
5. **Verify each child's self-report before proceeding.** Self-reports are
   not facts: re-check the commit sha exists, re-run the test command or
   inspect its output, stat the file. Only then dispatch the next phase.
6. **Child hit its tool-call cap? Harvest and re-dispatch — don't discard.**
   Subagents run on a call budget (~50 tool calls); a deep investigation can
   exhaust it BEFORE any code lands. The child reports honestly ("hit cap, no
   commit, tree clean") — that is a valid outcome, not a failed run.
   - The inline delegation result is TRUNCATED. Read the full summary at the
     path in its footer (`cache/delegation/subagent-summary-*.txt`) and/or
     the live transcript (`cache/delegation/live/<delegation_id>/task-0.log`)
     to extract the verified findings.
   - Re-dispatch a FRESH subagent with the investigation baked into the
     context, and say explicitly: "A previous agent did the investigation —
     trust it, do not re-derive, implement now." The cap-hit run becomes a
     head start instead of wasted time.
   - Before re-dispatching, check `git status` is clean / no half-applied
     changes from the cap-hit child (Phase 1 left an uncommitted test; the
     orchestrator committed it itself rather than re-dispatching for that).
7. **Orchestrator closes the loop itself** (docs → resolved, DB task closed
   WITH `--ref <sha>`, CI gate, push). Closing needs repo-level judgment —
   don't delegate it.
   - **Before merging several parallel branches, dry-run every merge without
     touching the tree**: `git merge-tree $(git merge-base main b) main b`
     prints `changed in both` blocks = the files that WILL conflict. Additive
     doc edits across branches (e.g. every branch appends to the same
     PROBLEMS.md) are the predictable case — resolve by combining sections at
     merge time, or have one branch own the shared file. Never assume
     "no code overlap" means "no conflict"; shared docs always overlap.
   - **Detect HOW main is protected before pushing.** The classic API
     (`gh api repos/O/R/branches/main/protection`) returns 404 "Branch not
     protected" even when the user set protection via a GitHub **ruleset**
     (Settings → Rules). Rulesets are the modern mechanism and the classic
     endpoint is blind to them. Always also check
     `gh api repos/O/R/rulesets` then `.../rulesets/<id>` — a ruleset with
     `target: branch`, `enforcement: active`, rules `pull_request` (1
     approval) + `non_fast_forward` + `deletion` normally means NO direct
     push to main. **BUT check `bypass_actors` before assuming you're
     blocked:** if the ruleset grants `RepositoryRole` (admin) with
     `bypass_mode: always`, the repo owner's direct push STILL SUCCEEDS —
     GitHub prints `remote: - Changes must be made through a pull request.`
     as an informational notice while accepting the push. (Hit 2026-08-06:
     user said "I set protection rules"; classic API said NOT PROTECTED; the
     ruleset listed `pull_request`, yet `git push origin main` succeeded
     because the owner has admin bypass. Since the user's instruction was
     "push if you can, else PR", the push was correct.) After ANY push that
     a ruleset "should have" blocked, VERIFY the remote actually moved:
     `git fetch origin && git rev-parse origin/main` must equal your local
     HEAD — do not trust the push's own success line alone, and only fall
     back to PR creation when origin/main did NOT move.
   - **Merge parallel branches locally, gate the merged tree, then hand the
     user ONE consolidated PR.** When main requires PR approval (ruleset or
     classic), don't open N sequential PRs that conflict with each other on
     shared files — merge all branches into local main yourself with
     `git merge --no-ff`, resolve conflicts, run the FULL gate on the merged
     tree, then push-or-PR the single result. The user approves once, not N
     times.
   - **Resolve auto-generated file conflicts by REGENERATING, not
     hand-merging.** If a repo has a generated index (REPO_MAP.md, lockfiles,
     manifests) that conflicts on merge, run its generator on the merged tree
     (`python3 scripts/gen-*.py`) and stage the output — the generator IS the
     correct resolution. Hand-stitching conflict markers in a generated file
     is wasted effort and often wrong. (REPO_MAP.md conflicted on all 3 of 4
     merges; regeneration resolved each in one step.)
   - **Additive conflicts → keep BOTH sides, then verify with the real
     gate.** Two branches adding different test suites to the same
     CMakeLists.txt (or different exclusions to the same CI script) are
     both-right: keep both blocks. BUT hand-resolution can leave orphaned
     fragments (a duplicated trailing block after the kept section) that
     break parsing — my first CMakeLists resolution left a stray
     `WIN32_EXECUTABLE OFF` that failed configure with `Parse error.
     Expected "(", got identifier with text "OFF"`. The full gate caught it.
     Rule: after ANY manual conflict resolution, diff-clean is NOT
     merge-valid — run the complete gate (`ci/run-ci.sh` or equivalent) on
     the merged tree before declaring the merge done. Format stage passing
     proves nothing about configure; configure passing proves nothing about
     tests. (Hit 2026-08-06: 4-branch merge into albdf main; gate caught my
     CMake resolution error on the first run; fixed, re-gated green.)

## Gates that work

| Phase | Gate example |
|---|---|
| RED test | New test FAILS for the right reason; suite otherwise green; committed |
| GREEN impl | Same test passes; full suite green; formula/approach documented in comment |
| No-regression | fetch/extract/search/golden unchanged vs baseline |
| Close | DB task closed with evidence sha; CI gate green; pushed |

## Pitfalls

- **Sequential phases cannot run in parallel** on the same repo — a later
  phase depends on the earlier commit. Dispatch phase N+1 only after
  verifying phase N's sha.
- **Parallel fix agents on ONE shared checkout WILL clobber each other —
  and the recovery is orchestrator consolidation, not re-dispatch.**
  Worktrees are the prescription (see Workflow §4), but when you dispatch
  several fix agents against the same working tree anyway (e.g. three M13
  fix workstreams on main), they collide: one agent's uncommitted edits
  break another's clean-baseline proof (WS-B's full-suite run failed on
  WS-C's uncommitted normalizer changes), agents withhold their edits to
  avoid clobbering siblings (WS-C designed the copy-path fix but never
  applied it), and NOBODY commits because the build is broken by the
  combined tree. Do NOT re-dispatch — the work is all present and correct,
  just uncommitted. Consolidate yourself, in this order:
  1. Read ALL full summaries (the truncated inline results hide the
     per-agent state); classify each as DONE-but-uncommitted vs DESIGNED-
     but-not-applied vs BLOCKED.
  2. Build the whole tree once with everything in it; fix the surface
     compile errors the agents left (missing includes, namespace prefixes —
     e.g. WS-C's test called `PDFRTLTextNormalizer` unqualified inside
     `namespace pdf`).
  3. Run the full suite; expect 2-3 failures that are TEST-EXPECTATION
     drift, not regressions: an old test may PIN the buggy behavior the fix
     removes (update the expectation + comment — that IS the fix's proof),
     a new test may fail because a sibling changed shared code. Debug the
     genuine failures against a CLEAN baseline when a sibling's uncommitted
     changes are the prime suspect (stash everything, rebuild, re-run).
  4. Apply the designed-but-unapplied edits yourself (the agent's report
     has the exact diff), add any missing includes.
  5. Commit in LOGICAL UNITS (never `git add -A` across three workstreams):
     one commit per workstream's files, with per-commit messages; run the
     repo-map generator between commits.
  6. Re-run the full gate on the clean committed tree; fix format gate by
     clang-formatting the NEW/edited files (agents often leave
     hand-formatted code the gate rejects); commit the format fix.
  (Hit 2026-08-07: M13 WS-A/B/C all hit tool caps leaving the tree with 8
  uncommitted fixes + 3 failing tests; consolidation produced 6 logical
  commits, all 16/16 green, and exposed a real pre-existing engine bug —
  see `pdf-text-engineering` S#3.)
- **"Plan exists" ≠ "work done".** The biggest recon trap: a design doc
  commit masquerading as progress. Always check for code + tests + DB
  status, not just docs.
- **"Task exists" ≠ "work missing" — the inverse trap.** A tracking-DB task
  can be stale in the OTHER direction: it says "wire upstream X" when X is
  already compiled, registered (static self-registration pattern), and
  responsive in the binary. Verify the actual capability with `binary cmd
  --help` + the command list before dispatching. If the wiring exists, the
  child's real job is verification + tests + evidence closure, not
  implementation — say so explicitly or the child re-derives what's done.
- **All children hitting the SAME blocker = orchestrator's problem, not the
  children's.** When two+ parallel children independently report the same
  pre-existing build/doc/environment failure, STOP dispatching more work on
  that base and fix it yourself on main (it is almost never a child error —
  it is a broken baseline you dispatched onto). Sequence that worked
  (2026-08-06): (1) children exhaust budget reporting the compile break with
  evidence; (2) orchestrator fixes the root cause on main, rebuilds from
  clean, gets the REAL full-suite green; (3) propagates the fix into each
  worktree by COPYING the file + committing per-branch (cherry-pick is
  finicky when children left uncommitted fix variants in the worktrees —
  `git checkout -- <file>` first, then copy, then commit); (4) re-dispatches
  fresh children with the investigation credited and the plan corrected
  ("the blocker is fixed on this branch: <sha>; a previous agent found X —
  trust it, do not re-derive"). Cap-hit children's summaries are the recon
  gift: read all of them BEFORE fixing — they may have found plan errors too
  (e.g. a CLI flag the plan invented).
- **Child summaries are self-reports.** "Committed", "tests pass", "pushed"
  from a child must be verified (git rev-parse, re-run test, check remote).
- **Cap-hit children still leave value.** A child that exhausts its tool
  budget mid-investigation (no code, no commit) produced verified findings —
  read the full summary file it left behind and re-dispatch with those baked
  in, instead of re-deriving or treating the run as wasted.
- **"Trust the design, don't re-derive" is NOT self-executing — budget-slice
  the child's recon explicitly.** A continuation child whose brief said
  "CONTINUATION — do NOT re-explore; trust the prior agent's verified design"
  still spent its ENTIRE ~50-call budget re-verifying every API signature and
  line number from source before writing any code (2026-08-08 M14 WS-B
  re-dispatch: tree left clean, zero commits, zero tests; the summary was
  honest but the run produced no progress). The re-verification is NOT wasted
  — it confirmed the design and caught one real gotcha (a compile-def gap) —
  but the orchestrator should have told the child: recon = branch + clean-tree
  check + the 2-3 anchor line numbers you will edit, THEN write the RED test;
  reserve at least half the budget for write/build/test/commit. Best: package
  the verified findings as a skill reference file under the project's umbrella
  (see albdf-fork-development `references/freetext-rtl-appearance-m14.md`) so
  the re-dispatch context can point at a durable artifact and the child only
  spot-checks it.
- **Missing report-back contract → vague results.** Demand exact output:
  test names, failure lines, pixel numbers, shas. Require "stop and report"
  on unexpected failures instead of silent workarounds.
- **Repo docs can lie about build layout** (e.g. root AGENTS.md says
  `cmake -S . -B build` but CMakeLists lives in `src/`). Verify the real
  build dir before writing commands into child contexts.
- **A child's confident root-cause claim is still a self-report — verify it
  with an independent oracle before accepting a "blocked" verdict.** In the
  P3 saga, a child spent two full runs on "the renderer paints marks as
  oversized blobs, the fix is structurally impossible from the emitter
  side" — the orchestrator's own Ghostscript pixel probes proved the
  "blob" was Latin 'A' painted by an invalid CIDToGIDMap (a spec bug in
  the emitter, 30-min fix). Children investigate inside the project's own
  assumptions; an independent tool (a second renderer, a strict spec
  checker, a packet capture) breaks that loop. When a child says
  "impossible / blocked by X", verify X directly before re-planning.
- **A self-consistent test suite hides wrong output.** Golden-image tests
  that compare the project's own renderer against committed baselines pass
  even when EVERY output is wrong (baselines were generated by the same
  buggy pipeline). If a child says "all tests pass, but pixels look wrong",
  the tests may be the problem — check with an independent consumer.
- **DB evidence-gated completion** (if the project has one): closing a task
  requires `--ref <sha>`; an un-evidenced "done" pollutes the source of
  truth.
- **"Push the branches so CI builds on GH infra" needs a PR, not a push.** A
  workflow with `on: pull_request:` + `push: branches: [main]` starts NO runs
  for a bare `git push -u origin feature`. The user's ask ("push branches and
  create a CI to see if it builds") hits this: pushes succeed, zero Actions
  runs. Check triggers first (`grep -A5 "^on:" .github/workflows/*.yml`) and
  say so plainly. Also: a working `ssh -T git@github.com` authenticates git
  only — `gh` CLI/REST API (create PR, check run status) need a separate
  credential. Bootstrap: `sudo apt-get install -y gh`, then device flow
  (`gh auth login` — user opens a browser) or a PAT (fine-grained: Contents
  R/W + Pull requests R/W + Actions read; classic: `repo` + `workflow`);
  store via `gh auth login --with-token < file`, never in the repo/memory.
 Public-repo API reads work unauthenticated (curl 200) but PR creation
 always needs the token. (Hit 2026-08-06: three branches pushed, no CI;
 `gh` absent, no PAT — the blocker is auth, and only the user can provide
 it. Ask, don't improvise.)
 - **Runs stuck in `queued` ≠ your config — check GitHub's status FIRST.** If
 `gh run list` shows runs queued for many minutes AND `gh run view <ID>
 --json jobs` lists the job names (workflow parsed, actions present on the
 branch), the likely cause is a GitHub Actions/Runner incident, not the
 workflow. Verify: `curl -s https://www.githubstatus.com/api/v2/status.json`
 → `"Partial System Outage"` / Actions component down. Correct response:
 WAIT (queued runs auto-start when the fleet recovers; no re-dispatch
 needed) and tell the user the verdict instead of debugging a healthy
 workflow. Only investigate your own config if runs remain queued AFTER the
 incident clears. (Hit 2026-08-06: three albdf PRs queued ~1h during a
 GitHub Partial System Outage; config was correct, runs started after.)
 **Productive alternative while runners are down: run the repo's OWN gate
 locally, one subagent per branch, SEQUENTIALLY.** Same 4-stage gate GitHub
 would run (`bash ci/run-ci.sh` — Release build+ctest, ASAN build+ctest,
 format), with the machine's real toolchain paths pinned in the context
 (e.g. `VCPKG_ROOT=/home/agent/vcpkg-cache/vcpkg` — the script's default is
 often wrong). Child contract: read-only (no commits, no pushes, no DB
 writes), background `notify_on_complete` for the long ASAN stage, exact
 per-stage numbers back. Run branches one at a time, not in parallel — N
 simultaneous ASAN rebuilds thrash the CPU and hide per-branch failures. A\n local gate failure is a REAL finding (it caught a determinism flake that\n GH CI would have caught too) — fix it on the base, propagate to all\n branches, re-verify.\n **Gate subagent went silent? Check for stuck, then take over directly.** A\n child that launched the long gate in the background and then shows NO new\n transcript lines for a long time (no stage progress, no summary file) is\n likely stuck — its background process died or it hung waiting. Verify:\n transcript tail, `ps aux | grep ci/run-ci`, the ASAN build-dir mtime\n (created at configure but never advancing = stuck). When confirmed, do NOT\n re-dispatch a fresh gate subagent — run the gate yourself in the worktree\n (deps are already built, dirs configured; a gate you can run directly\n beats another child round-trip). Give it a UNIQUE log path (`> /tmp/ci-run-\n <branch>.log 2>&1`): the repo's gate writes shared /tmp/ci-*.log names and\n concurrent/overlapping runs clobber each other's evidence. (Hit 2026-08-06:\n PR #4's gate subagent went silent 1.5h after launch; orchestrator ran the\n gate directly with its own log and got the result.)
- **Fine-grained PAT missing a scope → `Resource not accessible by personal
  access token (createPullRequest)` (403).** The token authenticates and
  reads the repo fine (gh auth status OK) but PR creation fails with that
  exact GraphQL/REST error. The fix is NOT a new token: edit the EXISTING
  fine-grained PAT's permissions at
  `https://github.com/settings/tokens?type=beta` (Repository access: the
  repo; Pull requests: Read and write; Actions: Read for `gh run list`).
  Permission edits apply to the current token string — the stored
  `~/.config/gh/hosts.yml` value keeps working without re-pasting. Only
  regenerate if GitHub forces it. After the user says "done", retry the
  exact failing command (create PR), then verify with `gh run list`.
  (Hit 2026-08-06: first PAT lacked PR write → 403; user edited perms, no
  new token needed → all three PRs created instantly.)
  **BEFORE asking the user to edit permissions, try REST: `gh pr create`
  uses GRAPHQL, and a fine-grained PAT can 403 on the GraphQL mutation
  while the REST endpoint succeeds with the same token.** Observed
  2026-08-07: `gh pr create` → `GraphQL: Resource not accessible by
  personal access token (createPullRequest)`; the identical operation via
  `curl -X POST -H "Authorization: Bearer $(gh auth token)" -H "Accept:
  application/vnd.github+json"
  https://api.github.com/repos/O/R/pulls -d '{"title":"...","head":"<branch>","base":"main","body":"..."}'`
  returned **201** with the very same token. Order of attack: (1) try
  `gh pr create`; (2) on createPullRequest 403, try the REST POST — if it
  works, done, no user round-trip; (3) only if BOTH fail, ask the user to
  bump the PAT scope. **Probe-PR cleanup trap:** a successful probe POST
  creates a REAL open PR — close it immediately
  (`curl -X PATCH .../pulls/<n> -d '{"state":"closed"}'`) before opening
  the real one, and list first (`.../pulls?state=open&head=O:<branch>`)
  to find the probe by its title.
- **Fine-grained PAT scope gap for RELEASES: `gh release create` 403s even
  after PR creation works.** Creating PRs needs only **Pull requests:
  read/write**; creating a **Release** additionally needs **Contents: read
  and write** (classic tokens: `repo` covers both). Symptom:
  `HTTP 403: Resource not accessible by personal access token` on
  `https://api.github.com/repos/O/R/releases` while `gh pr create` and
  `git push` both succeed. Fix: edit the existing fine-grained PAT
  (Contents → Read and write; the current token string keeps working, no
  re-paste). The TAG is pushed separately (`git push origin <tag>`) and
  needs no token — so the release commit is public even when the Release
  object is blocked. UI fallback: **Releases → Draft a new release → pick
  the pushed tag**. (Hit 2026-08-07: albdf 0.2.0 — PRs created fine, tag
  pushed, release create 403'd; user offered the UI path.)
  **"Admin" in a fine-grained PAT name is NOT admin — probe the scope.** The
  user may hand you a token and call it "the admin key" expecting it to do
  everything; fine-grained permissions are still whatever was ticked in the
  matrix. When a capability 403s, probe the REAL gap (a throwaway
  `curl -X PUT .../contents/__probe__.txt` for Contents:write, or the actual
  failing API) instead of re-trying the same command or assuming a new token
  fixes it. `gh api .../releases` returning 200 proves READ only, never
  write. Full recipe + probe in
  `references/release-declaration-recipe.md`. Full operation→permission
  matrix (push / PR / releases / Actions / branch protection / secrets) in
  `references/fine-grained-pat-permission-matrix.md` — check it BEFORE
  dispatching work that needs a GitHub capability.
- **Profile fields need the `user` scope; the release-capable classic PAT
  still 403s on PATCH /user without it.** Classic PAT with `repo` +
  `workflow` + `admin:org` can create PRs AND releases, but updating
  name/bio/company/location returns 404 with `gh: This API operation needs
  the "user" scope`. `gh auth refresh -h github.com -s user` runs a DEVICE
  flow: it prints a one-time code, then after approval ALSO prompts
  "Authenticate Git with your GitHub credentials? (Y/n)" — answer `n` (git
  stays on SSH). Trap: piping through `tail` hides the code (buffered), and
  a PTY background process can leave the git prompt unanswerable — run it
  foreground with the code visible, or pre-answer with
  `gh auth refresh -h github.com -s user <<< "n"` in background and read
  the code from the live transcript. Verify scope landed with
  `gh auth status | grep -i scopes` BEFORE retrying the PATCH. (Hit
  2026-08-07: two tokens 403'd on profile; device flow with `<<< "n"`
  granted `user`, fields then applied cleanly.)
- **A repo-scoped fine-grained PAT can CREATE a new repo but cannot WRITE to
  it — SSH is the account-level escape hatch.** `POST /user/repos` (create
  repo, e.g. a profile README repo `<username>/<username>`) succeeds because
  repo creation is account-level, but the very next
  `PUT /repos/O/R/contents/...` on that NEW repo fails
  `Resource not accessible by personal access token` (403) — fine-grained
  PATs only cover the repos explicitly selected at token creation, and the
  new repo isn't among them. The contents API and `git clone` over HTTPS
  both use that scope; only `git push` over **SSH** bypasses it (SSH keys
  are account-level and can write any repo the account owns). When a task
  needs to populate a repo that the PAT's repo-selection doesn't cover:
  `git remote set-url origin git@github.com:O/R.git` + push over SSH, no
  token edit needed. (Hit 2026-08-07: yolka-wiz profile README repo —
  created via fine-grained PAT, contents PUT 403'd, SSH push succeeded.
  Note: profile README repos must be named exactly `<username>/<username>`
  to render on the profile page.)

## Verification checklist

- [ ] Recon showed real state (git + DB + baseline tests), not doc claims
- [ ] Docs/DB updated to match reality before dispatch
- [ ] Execution plan has phases, files, commands, gates, risks
- [ ] Each child context is self-contained (path, AGENTS.md, build cmds, TDD, commit rules, report-back)
- [ ] Child shas/results verified, not believed
- [ ] Orchestrator closed docs/DB/CI/push itself

## References

- `references/albdf-wave-dispatch.md` — worked al-bdf example: DB reconcile
  recipe, parallel worktree setup, the vcpkg-path doc lie, and the binary
  command-list oracle for spotting already-wired "wire X" tasks.
- `references/merge-into-protected-main.md` — merging N parallel branches
  into a ruleset-protected main: detect rulesets (classic API lies), resolve
  auto-generated/additive conflicts, gate the merged tree (diff-clean is not
  merge-valid), then one consolidated PR.
- `references/release-declaration-recipe.md` — declaring a release end to end:
  version bump + future-proof smoke check, RELEASES.md/PLAN.md/DB updates,
  full gate on the release commit, deterministic artifact PROVEN by building
  twice, tag push, and the `gh release create` Contents:write token trap
  ("admin" fine-grained PAT ≠ admin; probe the scope, don't trust the label).
- `references/shared-tree-fix-consolidation-2026-08-07.md` — worked example
  of the shared-checkout pitfall: three M13 fix agents on ONE tree, all
  cap-hit with uncommitted work; the consolidation sequence (read all full
  summaries → build once → fix surface errors → diagnose the 3 failures as
  test-typo / expectation-pinning-bug / pre-existing-engine-bug → apply
  designed-but-unapplied edits → commit in logical units → clang-format the
  gate).

