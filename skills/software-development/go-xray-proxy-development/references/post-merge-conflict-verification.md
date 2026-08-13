# Post-Merge Conflict-Resolution Verification

> When a human (or another agent) merges overlapping PRs, the conflict
> resolution can be botched and land on `main` looking like a normal merge.
> Verify merged state before trusting it.

## Trigger

Two PRs touched the same files and a "Merge branch 'main' into feature"
commit appears between their merge commits. That commit is where a human
resolved conflicts by hand — the #1 spot for silent damage.

## Verification sequence

```bash
# 1. Merge history — find the manual conflict-resolution commit.
git log origin/main --oneline -10

# 2. Does the merged tree even compile? Fastest signal.
git fetch origin && git checkout origin/main   # detached
go build ./...   # or make / cargo build / etc.

# 3. Leftover conflict markers anywhere?
git grep -n '^<<<<<<<\|^=======\|^>>>>>>>' origin/main -- '*.go' '*.md'

# 4. Structural integrity of merged files — functions nested in functions,
#    brace imbalance, dropped entries.
git show origin/main:relay.go | sed -n '95,110p'
git grep -n "func tuneTCPConn" origin/main        # exactly one definition
git grep -n "func (r \*wanRelay) logAccess" origin/main  # single signature
```

## Reconstruction-diff method (the reliable part)

The original feature commits are still in your local object store after a
fetch — use them as the source of truth:

```bash
# A. Check both feature tips exist locally.
git cat-file -t <sha-a> && git cat-file -t <sha-b>

# B. Reconstruct the correct union in a scratch branch.
git checkout -b verify-correct-merge <base-sha>
git merge <sha-a> --no-edit    # may conflict; resolve by taking each
git merge <sha-b> --no-edit    # file from the branch that owns it
# or, per file: git checkout <sha-a> -- file.go

# C. Diff correct tree against what was actually merged.
git diff origin/main --stat    # the delta is exactly what the merge lost

# D. Build/test the reconstruction; only then write the repair.
go build ./... && go test ./... && go vet ./...
```

## Botched-resolution signatures (seen 2026-08-11, Viberoxy PRs #5+#6)

| Symptom | Root cause | Fix |
|---|---|---|
| `relayThroughWAN` doc comment + signature nested inside `directRelay`'s body → syntax error | conflict resolver pasted the other branch's function header into the body | delete the 5 stray lines |
| `XRAY_MUX` env block inside Router `if`, brace never closed → `parseConfig` broken | resolver merged blocks into each other, lost a `}` | close the `if`, restore block as its own |
| one PR's AGENTS.md entry line silently gone | resolver picked one side and dropped the other's doc line | re-add the dropped line |

## Repair pattern

- **Never re-do the feature PRs.** Build a minimal surgical fix branch off
  `origin/main` restoring the intended union (typically 3 files, ±5 lines).
- Verify `build + vet + test + race` on the repair branch.
- Open one repair PR titled to say it fixes a botched conflict resolution.
- Warn the maintainer: merge the repair before anyone pulls `main`.

## Anti-patterns

- Trusting "merged" status on GitHub without building the merged tree.
- Fixing by re-applying whole feature branches (re-introduces conflicts,
  bloats the diff).
- Writing the repair without first reconstructing the correct tree — you
  can't know what the botched merge lost until you diff against the union.
