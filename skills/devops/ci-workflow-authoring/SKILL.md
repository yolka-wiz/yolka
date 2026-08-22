---
name: ci-workflow-authoring
description: Author/parameterize GitHub Actions CI workflows.
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [ci, github-actions, workflows, nightly, fuzzing, cargo]
    related_skills: [github-pr-workflow, github-repo-management]
---

# CI Workflow Authoring (GitHub Actions)

## When to Use
Authoring or editing `.github/workflows/*.yml`; adding a longer (nightly) job
alongside an existing short PR job; making a deterministic test harness
configurable so both CI tiers share one entrypoint. Works for Rust (cargo) and
general runners.

## Core pattern: one entrypoint, short vs. long via env vars

When a PR-time job runs a short deterministic check (e.g. a seeded no-panic fuzz
smoke with a fixed iteration count) and you want a longer nightly run, do NOT
duplicate the logic in a second workflow. Instead:

1. **Parameterize the harness** in code with env vars that default to the
   short/PR-time values, keeping the SAME seed/PRNG so a given knob set is
   bit-for-bit reproducible:
   ```rust
   const MUTATIONS: usize = 400; // historical default → keeps seq identical
   fn env_or(default: usize, name: &str) -> usize {
       std::env::var(name).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
   }
   let iterations = env_or(MUTATIONS, "EXTFS_FUZZ_ITERATIONS");
   let max_flips  = env_or(MAX_FLIPS, "EXTFS_FUZZ_MAX_MUTATIONS");
   ```
   Key rule: the default MUST equal the previous constant and the RNG seed MUST
   not change, so existing short-CI results are unchanged while nightly dials
   the knobs up. Also `eprintln!` the active budget + seed so CI logs are
   auditable (pass `-- --nocapture` on the test command to surface it).

2. **Share one shell entrypoint** (e.g. `scripts/run-fuzz-smoke.sh`) that
   forwards/defaults the env vars:
   ```bash
   export EXTFS_FUZZ_ITERATIONS="${EXTFS_FUZZ_ITERATIONS:-400}"
   export EXTFS_FUZZ_MAX_MUTATIONS="${EXTFS_FUZZ_MAX_MUTATIONS:-5}"
   cargo test -p <crate> --test <name> --release -- --nocapture 2>&1 | tail -20
   ```

3. **Nightly workflow** sets larger values on the SAME step/script:
   ```yaml
   on:
     schedule: [{ cron: '0 4 * * *' }]
     workflow_dispatch: { inputs: { fuzz_iterations: { default: '5000' } } }
   ...
   - name: Long fuzz (release, nightly budget)
     env:
       EXTFS_FUZZ_ITERATIONS: ${{ github.event.inputs.fuzz_iterations || '5000' }}
       EXTFS_FUZZ_MAX_MUTATIONS: '12'
     run: ./scripts/run-fuzz-smoke.sh
   ```
   `github.event.inputs.X || 'default'` gives the default on schedule runs (where
   inputs are empty) and the user value on manual dispatch. Bound the budget so
   it stays in "a few minutes" on a 2-core runner; time it locally in release
   before committing a number.

## Verify locally, don't trust YAML/lint alone

Run the REAL gate changes locally before finishing: `cargo fmt --all -- --check`,
`cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`,
then run the shared script at BOTH budgets (default and nightly) and the
differential/extras the workflow calls. Time each so you can report real elapsed
numbers. Report exact commands and real output.

## Pitfalls

- **`write_file` strips the exec bit on shell scripts.** If a workflow invokes a
  script via `./scripts/x.sh`, a rewritten script comes out mode 100644 and CI
  fails with "Permission denied". After writing a CI entrypoint script, restore
  and verify: `chmod +x scripts/x.sh` then `git diff --summary` should show
  `mode change 100644 => 100755`. Check `git ls-files -s` / `git ls-tree HEAD`
  for the committed mode.
- **Parallel-agent edits land in the same working tree.** If other agents work
  on the same repo concurrently (e.g. a cargo-audit sibling editing
  `Cargo.lock`, `Cargo.toml`, and another workflow), `git status` will show
  files you never touched. Inspect with `git diff <file>` BEFORE assuming
  ownership; leave the sibling's files untouched and restrict yourself to the
  files you were assigned. Don't revert or "fix" their changes.
- **Don't alter existing workflow steps' behavior** unless you've confirmed a
  real bug; prefer APPENDING new jobs/steps or pointing them at a shared script
  that preserves the default behavior.
- House rules often forbid touching `Cargo.toml`/`Cargo.lock`/other crates when
  a git-touching sibling runs in parallel — scope your edits and verify with a
  final `git status --short` that you changed exactly your files.

## Related
- `github-pr-workflow` — the PR lifecycle (branch/commit/open/merge) around CI.
- `github-repo-management` — repos, remotes, releases.
