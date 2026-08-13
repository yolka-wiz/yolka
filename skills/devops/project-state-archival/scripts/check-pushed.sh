#!/usr/bin/env bash
# Verify every local branch of a repo is fully pushed to its origin.
# Reliable check that catches worktree branches and stale refs.
# Usage: check-pushed.sh <repo-dir> [<remote=origin>]
# Exit 0 = all branches pushed. Non-zero + printed "UNPUSHED" lines = action needed.
set -u
repo="${1:?usage: check-pushed.sh <repo-dir> [remote]}"
remote="${2:-origin}"

cd "$repo" || { echo "cannot cd: $repo"; exit 2; }
[ -d .git ] || [ -f .git ] || { echo "not a git repo (or worktree): $repo"; exit 2; }

echo "== $repo (remote=$remote) =="
git fetch "$remote" 2>/dev/null
fetch_rc=$?
[ $fetch_rc -ne 0 ] && echo "WARN: fetch failed (rc=$fetch_rc); using stale remote refs"

# gather local branches: checked-out ones and plain local refs
branches=$(git for-each-ref --format='%(refname:short)' refs/heads)
rc=0
for b in $branches; do
  if git rev-parse --verify -q "$remote/$b" >/dev/null 2>&1; then
    n=$(git rev-list --count "$remote/$b".."$b" 2>/dev/null)
    case "$n" in
      ''|*[!0-9]*) n=-1 ;;
    esac
    if [ "$n" -gt 0 ]; then
      echo "UNPUSHED: $b ($n commits ahead of $remote/$b)"
      rc=1
    else
      echo "  ok:     $b (in sync)"
    fi
  else
    echo "UNPUSHED: $b (no remote branch $remote/$b exists)"
    rc=1
  fi
done

# also flag untracked files that might be real state
untracked=$(git status --porcelain | grep '^??')
if [ -n "$untracked" ]; then
  echo "UNTRACKED (review before delete):"
  echo "$untracked"
fi

exit $rc
