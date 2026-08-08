---
name: git-secret-purge
description: "Purge pushed secrets from git history; recover clones after force-pushed rewrites."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, security, secrets, history, filter-repo]
    related_skills: [github-repo-management, git-essentials]
---

# Git Secret Purge

Removing a credential from the working tree is NOT enough — the value stays in
every historical commit. Rewriting history with `git-filter-repo` is the
reliable way to scrub a secret from the full commit graph.

## When to Use

- An API key / token / password was committed and pushed (repo may be public).
- User says "purge the api key from repo".
- A live credential appears in `git log -S <secret>`.

## Workflow

```bash
# 1. Install git-filter-repo into a venv (not system pip under PEP 668)
uv pip install --python /path/to/venv/bin/python git-filter-repo

# 2. Mapping file: old==>new  (one pair per line)
printf 'sk-XXXXXXXXXXXXXXXX==>***REDACTED: KEY_NAME***\n' > /tmp/replace.txt

# 3. Rewrite history. --force is REQUIRED when the clone isn't pristine
#    (gitignored files count as untracked changes, even with clean git status)
git-filter-repo --replace-text /tmp/replace.txt --force

# 4. filter-repo REMOVES the origin remote — re-add it
git remote add origin git@github.com:owner/repo.git

# 5. Verify before pushing
git log --all --oneline -S "sk-XXXX"        # empty = purged
git grep -l "sk-XXXX" $(git rev-list --all) # empty = purged

# 6. Force-push (fetch first: --force-with-lease needs a fresh ref)
git fetch origin
git push --force origin main
```

## Pitfalls

1. **Every commit sha changes.** After a rewrite, all doc references to old
   shas (RELEASES.md, PLAN.md, PROBLEMS.md, ci scripts) dangle. Remap them by
   subject with a dict built from `git log --oneline --reverse` — never guess.
2. **`--replace-text` doesn't fix the working tree file.** The doc that held
   the key still shows the raw value or the replacement placeholder. Rewrite
   that file to reference config/env instead of embedding a key, and commit.
3. **Containment ≠ revocation.** Anyone who cloned before the purge still has
   the key — on a public repo it's already exposed. ALWAYS tell the user to
   rotate the credential at the provider; history rewrite is not enough.
4. **CRLF files (vendored upstream).** A text-mode rewrite normalizes
   line endings → whole-file diff churn. Do byte-level replace instead:
   `data = open(p,'rb').read(); open(p,'wb').write(data.replace(b"old",b"new"))`.
5. **Force-push invalidates other clones.** Stale clones must NOT blindly
   re-clone or `git pull` (pull refuses on divergent history). See
   "Collaborator recovery" below.

## Collaborator recovery (receiving a force-push)

When a rewritten remote is fetched, `git fetch` reports `forced update` and
`git pull` refuses. The correct sync protocol — verify first, then align:

```bash
# 1. Which of my commits are not on the remote?
git log --oneline origin/main..HEAD

# 2. If the rewrite only re-numbered commits (same messages/trees), find the
#    rewritten twin of your local tip and confirm content identity:
git diff --stat <local-tip> <rewritten-twin>   # empty = pure history rewrite
git status --porcelain                          # working tree must be clean

# 3. Only then align:
git reset --hard origin/main
```

- **Content identity, not message equality**: `git diff --stat <local> <rewritten>` empty means nothing of yours was lost — safe to reset.
- **Rewritten commits are indistinguishable from new ones by SHA alone.** To tell whether a file change is genuinely new, compare per-path histories and trees:
  ```bash
  git log --oneline <old-local> -- <path>
  git log --oneline <old-local>..<remote> -- <path>
  git diff --quiet <old-local> <remote> -- <path> && echo IDENTICAL
  ```
- **Hardcoded commit SHAs in CI configs** (e.g. a format-gate fork base) silently break after a rewrite — grep CI/scripts for SHA constants after any `forced update`.
- **Stale branch refs fool `merge-base --is-ancestor`.** After a rewrite, branches
  that were already merged show "NOT merged" because their commit SHAs were
  renumbered. Do NOT trust ancestry checks on rewritten repos — compare by
  subject instead:
  ```bash
  for b in feature/foo feature/bar; do
    echo "== $b =="
    git log --format=%s origin/main..origin/$b | head -10   # empty subjects = ref is stale
  done
  # If the subjects already exist in main's history, the branch ref is stale → delete.
  git diff --quiet origin/feature/foo origin/main && echo "same tree (content merged)"
  ```
  This bit hard on 2026-08-06: `feature/wave1-core`/`wave1-infra` refs were
  pre-rewrite SHAs of content already in main; merge-base said "NOT merged" while
  the diff of tree contents said otherwise.
- **Tags move too.** After a rewrite, `git tag -l` still lists tags; verify a tag
  points at a post-rewrite commit with `git log -1 <tag>` and re-push tags that
  point at old SHAs.
6. **Tags survive but their targets move.** `git tag -l` still shows tags;
   references to the old tag sha in docs must be re-resolved.
7. **filter-repo on a non-fresh clone** aborts with "you have untracked
   changes" even when `git status` is clean — ignored files trigger it. Use
   `--force` on repos you control.

## Verification Checklist

- `git log --all --oneline -S "<secret>"` → empty
- `git ls-remote origin main` == `git rev-parse HEAD`
- The doc file that contained the key is rewritten to use env/config
- User informed: rotate the key at the provider

## References

- Session example (2026-08-05): context7 `ctx7sk-*` key purged from
  yolka-wiz/al-bdf-engine, 44 commits rewritten, doc rewritten to use
  `hermes config set`, sha references remapped across 5 doc files.
