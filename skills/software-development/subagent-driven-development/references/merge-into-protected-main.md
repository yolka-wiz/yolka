# Merging parallel branches into a ruleset-protected main

Worked example (2026-08-06, al-bdf-engine): four M10 branches (search,
redaction, fuzz, render-fix) all locally gated green; user set GitHub
protection and said "merge into main; if you cannot push, create a PR and I
will accept it."

## 1. Detect protection BEFORE attempting push

Classic API lies when protection is a ruleset:

```bash
# Classic — returns 404 "Branch not protected" even when ruleset blocks push
gh api repos/O/R/branches/main/protection        # 404 = NOT classic-protected

# Rulesets — the modern mechanism; check these too
gh api repos/O/R/rulesets                        # list: name, target, enforcement
gh api repos/O/R/rulesets/<id>                   # detail: rules, conditions
```

A ruleset with `target: branch`, `enforcement: active`, conditions
`include: [~DEFAULT_BRANCH]`, and rules `pull_request` (required_approving_
review_count 1) + `non_fast_forward` + `deletion` means: **no direct push to
main, no force-push, PR + approval required**. Don't waste a push attempt.

## 2. Merge all branches into LOCAL main (--no-ff)

```bash
git merge --no-ff m10/branch-a -m "Merge m10/branch-a: <summary>"
# repeat for each branch; resolve conflicts as they come
```

Conflict patterns seen:

- **Auto-generated index (REPO_MAP.md)** — conflicted on 3 of 4 merges.
  Resolve by regenerating, never hand-merging:
  `python3 scripts/gen-repo-map.py && git add REPO_MAP.md`
- **Shared docs (docs/PROBLEMS.md)** — additive; git auto-merges when
  hunks don't overlap, otherwise combine sections.
- **Shared build files (UnitTests/CMakeLists.txt, ci/run-ci.sh)** — additive
  on both sides (two new test suites; three format exclusions). Keep BOTH
  blocks. Script the resolution with exact-string replacement, then verify:
  ```bash
  grep -c "<<<<<<<" <file>      # must be 0
  ```

## 3. THE TRAP: diff-clean is not merge-valid

First resolution of CMakeLists.txt left an orphaned trailing fragment
(`WIN32_EXECUTABLE OFF ...`) after the kept `set_target_properties` block.
Gate run 1 failed at configure on BOTH builds:

```
CMake Error at UnitTests/CMakeLists.txt:278:
  Parse error.  Expected "(", got identifier with text "OFF".
```

Format stage passed (41 files) — irrelevant. The fix was deleting the
orphaned fragment and re-gating. **Always run the FULL gate on the merged
tree; no stage result implies another stage.**

## 4. Gate the merged tree, then PR

```bash
bash ci/run-ci.sh > /tmp/ci-run-main-merged.log 2>&1   # background + notify
```

Then, because main requires PR approval, push the merged main as a single
PR (or a consolidated branch) for the user to accept — one approval covers
all four feature branches. The per-feature PRs become redundant once the
consolidated merge lands.

## Key numbers from the worked run

- 4 merges, 3 REPO_MAP conflicts (regenerated each), 2 real additive
  conflicts (CMakeLists, run-ci.sh) resolved keeping both sides
- gate run 1: FAILED (my CMake resolution error) → fixed → gate run 2:
  ALL GREEN (Release + ASAN + format)
- ruleset detected via `/rulesets` after classic API said "not protected"
