---
name: git-push-troubleshooting
description: "Diagnose failing/hanging git pushes; bootstrap empty remote."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [git, push, github, fork, bootstrap, network, troubleshooting]
    related_skills: [git-essentials, github-repo-management]
---

# Git Push Troubleshooting & Remote Bootstrap

When a `git push` fails or hangs, work the diagnosis ladder below before
assuming corruption or a network outage. Also covers the classic "first push
to an EMPTY remote needs to upload the whole tree" trap and how to avoid it.

## Why a push can be huge (snapshot, not diff)

Git commits reference the **full tree**, not a diff. Pushing branch `B` to a
remote sends every object the remote lacks that is reachable from `B`. If the
remote is **empty**, the first push uploads the *entire snapshot* — LibreOffice
core was ~350 MB compressed (149k objects) for a fix that changed one file.
The small diff is irrelevant; the missing *base* is what gets uploaded.

## Avoid re-uploading the world — the fork bootstrap

To make pushes tiny, get the base onto the remote **server-side** so your link
never carries it:

- **Fork upstream into the target repo** (`gh repo fork <upstream> --fork-name
  <name> --clone=false`). GitHub copies full history server-side; afterwards a
  branch push is only the objects that differ (`git rev-list --objects <branch>
  --not --remotes=origin | wc -l` — should be a handful).
- If the target repo name is taken, rename the empty one out of the way
  (`gh api -X PATCH repos/owner/name -f name=newname`), then rename the fork
  onto the freed name. Repo `DELETE` needs the `delete_repo` scope — a classic
  PAT without it fails with 403; rename does not.
- GitHub's repo **import API is deprecated** (404 → web-only tool at
  https://github.com/new/import). Fork is the scriptable path.

## Diagnosis ladder (push fails/hangs)

1. **`git push --dry-run`** — if it succeeds, negotiation is fine and the
   problem is the actual transfer / server receive-pack. If it fails, the refs
   or object enumeration are at fault.
2. **Control push to a known-good small repo** (e.g. a results repo you push to
   routinely). If that works, the problem is specific to the *target* repo (big
   remote / fork), NOT a global IP throttle. This one probe rules out a whole
   class of causes.
3. **Reproduce GitHub's check locally**: build the exact pack and strict-index
   it — `echo <branch> | git pack-objects --revs --stdout --thin > p.pack` then
   `git index-pack --strict --stdin < p.pack`. If it passes locally, your pack
   is valid and `remote: fatal: did not receive expected object <sha>` is the
   server aborting a big/flaky transfer — NOT local corruption. Do not chase
   local corruption when `git fsck --full` + `git verify-pack` are clean.
4. **Count what's actually missing**: `git rev-list --objects <branch> --not
   --remotes=origin | wc -l`. Tiny = the pack should fly once the link cooperates.
5. **Clean garbage**: failed fetches leave `tmp_pack_*` files —
   `rm .git/objects/pack/tmp_pack_*`. Note `git index-pack --stdin` imports a
   pack into your object DB (a duplicate ~same-size pack appears) — delete it
   afterwards.

## Pitfalls

- **`git rev-list --objects X | git pack-objects --stdout` breaks**: the root
  tree line has a trailing space → `fatal: bad revision '<sha> '`. Use the
  canonical `echo <branch> | git pack-objects --revs --stdout` instead.
- **`git fsck` on a shallow clone only validates reachable objects.** A reported
  `missing tree 4b825dc...` (the well-known EMPTY tree) can be your own
  `git commit-tree` test artifact created via `hash-object` WITHOUT `-w` (hash
  printed, object never stored). Not a real snapshot problem.
- **Shallow local → full remote**: negotiation is fine but the server's
  receive-pack on a multi-GB / many-refs repo can be slow; the response may be
  dropped by a flaky link. Give the push a LONG timeout (300–400s) before
  concluding it is stuck — short timeouts (90–120s) misclassify a slow server
  as a hard failure.
- **A hanging network tool in an autonomous agent**: give git tools a hard
  timeout (e.g. 120s) and VERIFY the ref landed (`git ls-remote origin
  refs/heads/<b>` contains it) before reporting success — otherwise a hung push
  burns the whole step budget and can be misreported as pushed.
- **Asymmetric link**: downloads (clone, ls-remote, api.github.com) can work
  while sustained uploads hang. The proxy may or may not help; test a control
  push rather than assume.

## Bounded history when `--unshallow` fails

Full unshallow of a huge repo repeatedly dies (`early EOF`,
`invalid index-pack output`). Fetch a bounded window instead:
`git fetch origin master --shallow-since=2025-08-01` (~1yr) or `--depth=200`
(a few days). Harden first:
`git config http.postBuffer 524288000; git config http.lowSpeedTime 600;
git config http.version HTTP/1.1`. Enough for `git log`/`git blame` in a recent
window without the multi-GB pack.

## Verification

- `git push --dry-run origin <branch>` → exit 0
- `git ls-remote origin refs/heads/<branch>` → lists the pushed sha
- control push to a small known-good repo → exit 0
