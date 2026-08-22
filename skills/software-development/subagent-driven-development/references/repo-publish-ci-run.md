# Publishing a fresh repo so CI actually runs (extfs-macos 2026-08-20)

Orchestrator closing the loop: when the user says "make sure the repo is live
on GitHub", the deliverable is NOT "pushed and 0 runs" — it is a pushed repo
with at least one real, witnessed workflow run. Two traps bit this exact flow.

## Trap 1: committed scripts missing the executable bit → CI fails `Permission denied`

A fresh checkout materializes git's recorded file modes. `scripts/foo.sh` /
`foo.py` committed with mode `100644` (non-executable) runs fine locally
(the working tree happened to have `+x`) but on the runner
`./scripts/generate-fixtures.sh` fails:

```
.../setup.sh: line 1: ./scripts/generate-fixtures.sh: Permission denied
##[error]Process completed with exit code 126.
```

Diagnose which files are wrong BEFORE/after a failed CI run:

```bash
git ls-files -s 'scripts/*' | awk '{print $1, $4}'   # 100755 = ok, 100644 = not executable
for f in scripts/*.sh scripts/*.py; do [ -f "$f" ] && [ ! -x "$f" ] && echo "NEEDS +x: $f"; done
```

Fix and commit so the mode is recorded:

```bash
chmod +x scripts/compare-manifest.sh scripts/generate-fixtures.sh scripts/test-linux-fuse.sh scripts/check-licenses.py
git add scripts/ && git commit -m "fix(ci): mark scripts executable for fresh checkout"
git push origin main
git ls-files -s 'scripts/*' | awk '{print $1, $4}'   # now 100755
```

Lesson: any executable helper a workflow invokes as `./scripts/...` must be
mode `100755` in the **index**, not just the local tree.

## Trap 2: creating a repo + pushing can leave ZERO workflow runs

`gh repo create <owner>/<name> --public --source=. --remote=origin --push`
pushes the current branch (often `master` if you didn't `git init -b main`).
But the workflows trigger on `branches: [main]`, so that push fires nothing,
and right after rename+push the run registry can still show 0 (workflows
register async on a brand-new repo).

Verify a run actually registered; don't trust the push alone:

```bash
gh api repos/O/R/actions/workflows -q '.total_count'          # workflows recognized?
gh run list --repo O/R -L 10                                    # any runs at all?
```

If `total_count` is 0 or runs don't appear, the reliable kick is to add a
`workflow_dispatch:` trigger to the workflow (useful anyway for manual runs),
commit, push, and re-check:

```yaml
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
```

Then re-list runs. If the linux/macos runs are `completed`/`success`, verify
the JOB and STEP conclusions are all green (not just the run summary), e.g.
`gh run view <id> --repo O/R --json jobs -q '.jobs[]|.name+" "+.conclusion'`
and per-step. A green run column can still hide a skipped fuse-smoke job.

## Also useful when publishing

- Set `/tests/fixtures/` + `/tests/manifests/` in `.gitignore` so generated
  fixture images/manifests don't get committed; the CI job regenerates them.
- `grep -A5 "^on:" .github/workflows/*.yml` before pushing to confirm the
  branch trigger matches the branch you push (see the existing
  "push needs a PR, not a push" pitfall for `on: pull_request:` workflows).
- Fix a stale upstream ref after a rename: `git branch --set-upstream-to=origin/main main`.
