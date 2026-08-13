# Server-migration handoff — albdf 0.3.0 → new server (2026-08-08)

User: "stop the development, upload your full current plan and issues and
updated db to github, we want to move you to a better server ... make sure
everything is remote on github, create a repository on github for exporting
your profile."

Goal: zero-loss handoff where the new server resumes from GitHub alone.

## Sequence that worked (exact commands)

1. **Stop dev + assess state first** (don't touch anything before knowing
   what's in flight):
   - `git worktree list` — find WIP branches with uncommitted work.
   - `git status --porcelain` per worktree — children often leave uncommitted
     GREEN implementations when they hit tool caps (WS-B left ~116 lines of
     FreeText RTL AP implementation + header + test uncommitted).
   - `gh issue list` / `python3 scripts/db.py status` — know the tracking
     state (issues = DB tasks here; DB file itself is gitignored!).

2. **Preserve WIP on its branches (never main):**
   ```bash
   cd <worktree> && git add <files> && \
   git -c user.name=yolka -c user.email=... commit -m \
     "wip(<area>): <what> (in progress, handoff)"
   git push -u origin m14/<branch>
   ```
   Mark clearly "(in progress, handoff)" so the resume knows it's unverified.

3. **Update the tracking DB with migration state** (open tasks = resume
   queue), then export it — the gitignored DB is THE classic migration loss:
   ```bash
   python3 scripts/db.py task-add --component core-agent --title "... M14 ..." --priority 1 --assignee yolka --notes "Branch m14/...; handoff 2026-08-08."
   git checkout -b handoff-migration
   git add -f db/albdf.db && git commit -m "chore(handoff): push gitignored task DB"
   git push -u origin handoff-migration && git checkout main
   git show origin/handoff-migration:db/albdf.db | head -c 16   # == 'SQLite format 3'
   ```

4. **Copy plan docs INTO the repo** — `.hermes/plans/*.md` lives outside the
   repo and dies with the machine:
   ```bash
   mkdir -p plans/handoff && cp ~/.hermes/plans/*.md plans/handoff/
   ```
   Write `plans/handoff/2026-08-08-handoff.md`: repo table, branch states +
   SHAs, open task numbers, resume checklist, credentials policy, open items.

5. **Refresh the profile export repo** (yolka-wiz/yolka): SOUL.md, memories,
   skills, config. rsync is often missing on Debian — `rm -rf skills &&
   cp -r <live>/skills skills`. **Secrets policy: NEVER copy the live
   config.yaml verbatim** — it carries a live context7 key; keep the repo's
   redacted template. Grep for real token shapes before pushing:
   ```bash
   grep -rnE 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|ctx7sk[0-9a-f]{20,}|AKIA[A-Z0-9]{16}' <exported>
   ```
   (plain `Bearer ` in doc examples is fine — `<key>` placeholders.)

6. **Final verification loop — never trust a push line alone:**
   ```bash
   git ls-remote --heads origin        # ALL branches incl. handoff-migration + WIP branches
   git ls-remote --tags origin         # release tags present
   git show origin/handoff-migration:db/albdf.db | head -c 16   # SQLite header
   git log --oneline origin/m14/<branch> -2                     # WIP commits present
   cd <profile-repo> && git status --porcelain                  # empty after push
   ```

## Lessons

- **Preserve WIP before anything else.** A cap-hit child's uncommitted GREEN
  work is real value; committing it as WIP on the branch makes resume cheap.
- **The gitignored DB needs an explicit export path** — a dedicated branch is
  better than force-adding to main (keeps main's history clean, restorable
  with one `git show`).
- **Plans outside the repo are migration casualties** unless copied in.
- **Credentials never travel in repos** — `~/.config/gh/hosts.yml`,
  fine-grained PATs, admin tokens, SSH keys are manual-copy items; say so in
  the handoff doc so the new server's operator knows what to bring.
- **The profile repo exists for exactly this** (yolka-wiz/yolka,
  `build-identity.sh` refreshes) — refresh it as part of any migration.
