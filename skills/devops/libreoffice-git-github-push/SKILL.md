---
name: libreoffice-git-github-push
description: "GitHub push gotchas: slow receive-pack, fork bootstrap."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [git, github, push, libreoffice, large-repo, fork, timeout]
    related_skills: [lo-autonomous-bug-cluster]
---

# LibreOffice / Large-Repo Git+GitHub Push Gotchas

Hard-won lessons pushing branches to a large GitHub repo (LibreOffice fork,
~6.9 GB, ~2000 refs) over a flaky link. Verified 2026-08-10.

## The core gotcha: receive-pack is SLOW on big repos

A push to a **large repo** — even a tiny 7-object pack — can take GitHub
**several minutes** of server-side `receive-pack`/`index-pack` before the
ref is accepted. On a normal repo it's instant, so you won't expect it.

- `git push --dry-run` **succeeds instantly** (negotiation only, no upload) —
  so negotiation is NOT the bottleneck.
- The actual upload/receive-pack hangs → short timeouts (90–120 s) abort it.
- **Fix: use a long timeout for the push** (300 s+). Once it lands, it's fast
  afterward (subsequent pushes of the same base are quick).
- Validate the pack locally to rule out local corruption:
  `git rev-list --objects master | git pack-objects --revs --stdout --thin |
  git index-pack --strict --stdin` (note: `--revs` reads ref names, not the
  `rev-list` line stream — the root-tree line has a trailing space and breaks
  naive piping).

## Empty-repo bootstrap: fork server-side instead of uploading the snapshot

Pushing a commit to an **empty repo** uploads its ENTIRE reachable object set
(the whole LibreOffice tree, ~350 MB) because git sends snapshots, not diffs.
This huge transfer is what keeps dying on flaky links.

- **Do NOT try to push the snapshot.** Instead, **fork the upstream repo
  server-side** so GitHub copies all base objects on their infra:
  `gh repo fork LibreOffice/core --fork-name libreoffice-work --clone=false`
- Then your work branch push is a tiny delta (e.g. 7 objects) — but see the
  slow-receive-pack gotcha above.
- If the target name is taken: **rename the empty repo out of the way**
  (`gh api -X PATCH repos/OWNER/NAME -f name=new-name`), then rename the fork
  into the freed name. `delete_repo` scope may be missing — rename works with
  `repo` scope, delete doesn't.
- Verify the fork really has the base before pushing:
  `git rev-list --objects <branch> --not --remotes=origin | wc -l` → should be tiny.

## Upload vs download asymmetry on flaky links

Downloads (clone, fetch, ls-remote) may work fine while **uploads hang**.
Don't assume a global network outage:
- If `gh api` (api.github.com) and pushes to a *small* repo work but pushes to
  the big repo hang → it's target-specific (receive-pack slowness), not a block.
- Probe a known-good small repo to isolate systemic vs specific:
  push a throwaway commit to a small repo you control, then force-remove it.

## Verification discipline

- Never trust "pushed" output. After a push, verify the ref exists:
  `git ls-remote origin refs/heads/<branch>` or the GitHub API
  (`gh api repos/OWNER/REPO/branches/<branch>`).
- SSH vs HTTPS: try both. For github.com, `gh auth setup-git` provides a
  credential helper for HTTPS; SSH key auth also works. Add
  `-o ConnectTimeout=15 -o ServerAliveInterval=15 -o TCPKeepAlive=yes` to
  `GIT_SSH_COMMAND` so a stuck connection fails fast instead of hanging forever.
