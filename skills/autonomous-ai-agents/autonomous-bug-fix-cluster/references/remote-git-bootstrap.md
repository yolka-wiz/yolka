# Remote-git troubleshooting (flaky links, empty origins)

## Bootstrap an empty origin work repo without a huge upload

Symptom: pushing a big snapshot (350 MB+) to an empty GitHub repo fails —
`remote unpack failed: index-pack failed` / `did not receive expected object`
even when the local pack verifies (`git fsck`, `git verify-pack`). Big
downloads work; sustained uploads drop on flaky links.

Working bootstrap (no local upload):
1. `gh repo fork <upstream> --fork-name <target> --clone=false` — server-side
   full history copy. If the target name is taken by the empty repo, first
   rename it away (delete often fails: token lacks `delete_repo` scope;
   **rename works** with repo scope):
   `gh api -X PATCH repos/<owner>/<old> -f name=<parked-name>`
   then rename the fork into the free name.
2. Point the work clone's origin at the fork (SSH URL for reliability).
3. Now branches whose parent is in the fork's history push as TINY deltas —
   verify with `git rev-list --objects <branch> --not --remotes=origin | wc -l`.

Note: GitHub's repo import REST endpoint is deprecated (web tool only).

## Reproduce a remote push failure locally

```bash
echo master | git pack-objects --revs --stdout --thin > /tmp/p.pack
git index-pack --strict --stdin < /tmp/p.pack   # same check GitHub runs
```
- If index-pack passes locally, the local DB is fine → remote failure is
  transport (truncation) or GitHub-side throttle, not corruption.
- Pitfall 1: do NOT pipe `git rev-list --objects master | git pack-objects` —
  the root-tree line has a trailing space → `bad revision` false failure. Use
  `--revs` + ref names.
- Pitfall 2: `git index-pack --stdin` imports the pack into `.git/objects/pack`
  — clean up the created pack-*.{pack,idx,rev} files afterwards (or run in a
  scratch clone).

## Throttle diagnosis

Signature: `gh api` / api.github.com work; downloads and `ls-remote` work;
git-protocol uploads (SSH, HTTPS, SOCKS5 proxy) all hang/timeout. → egress IP
throttled after repeated failed large pushes. Back off; schedule a retry
(one-shot cron with a retry script) instead of hammering.

## Bounded history when `--unshallow` fails

Full unshallow (multi-GB pack) dies with `early EOF`/`invalid index-pack` on
flaky links. Use bounded fetches:
- `git fetch origin master --shallow-since=YYYY-MM-DD` (~1 year of history)
- `git fetch origin master --depth=200` (a few days) — small packs survive.
Harden first: `git config http.postBuffer 524288000; http.lowSpeedTime 600;
http.version HTTP/1.1`.
After deepen, local HEAD stays at the old tip — compare with
`git rev-list --count HEAD..origin/master`; sweep "recent upstream work" with
`git log origin/master -- <path>` (in-flight work still needs Gerrit
open-changes, which local history never shows).
