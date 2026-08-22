---
name: ci-gate-hardening
description: Use when a CI step swallows tool exit code and may not gate.
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [ci, github-actions, cargo-audit, security-scan, gate]
    related_skills: [security-auditor, github-code-review, differential-review]
---

# CI Gate Hardening

The most common fake gate is a CI step that *looks* like it checks something but
can never fail: `cargo audit 2>/dev/null || echo "skipped"` swallows the tool's
exit code, so the job is green even when a real vulnerability exists. Often these
steps were copy-pasted from another repo and never actually executed once in CI.

## When to Use
- A workflow step pipes output to `/dev/null` or appends `|| echo ... || true`
  that masks the *tool's* exit code (as opposed to tolerating an install flake).
- An audit/scan/lint step "was added but never run" — the binary isn't even
  installed on the runner.
- Any CI gate whose failure mode you cannot demonstrate.

## Workflow
1. **Read the step verbatim.** Any `|| echo skip` / `2>/dev/null || true` after
   the *actual check command* means it cannot gate. Flag it.
2. **Run the tool locally first** to get real findings you can report verbatim
   before touching CI. Install it; don't trust the existing step.
3. **Prove the gate fails on a genuine finding** — confirm the tool's exit code
   is non-zero when a real issue exists, and zero when clean.
4. **Rework the step** with the real-gate shape (below).
5. **Run the surrounding workspace gate** (fmt / clippy / test) and the new step
   itself; report real output.

## The real-gate step shape (shell)
Install flake = tolerably transient; audit/check failure = must fail the job.
```yaml
- name: Security audit (cargo-audit)
  run: |
    # Transient install flake is tolerated (warn + skip, so CI isn't flaky),
    # but the check itself MUST run and its exit code is enforced.
    if cargo install cargo-audit --locked; then
      cargo audit || exit $?
    else
      echo "::warning::cargo-audit install failed (network/registry flake); audit skipped this run"
    fi
```
Key rules:
- **Never** `|| echo skip` / redirect to `/dev/null` on the *check* command — that
  is what makes a gate fake. Enforce its exit code (`|| exit $?` or `set -e`).
- If you must tolerate install/network flakiness, guard **only the install** with
  an `if`/else and emit a `::warning::` annotation so the skip is visible, never silent.
- GitHub Actions default shell is `bash -e`, so any failing unguarded command
  already fails the job; make sure set -e isn't being defeated by swallows.

## Pitfalls
- **Silent swallow tells you to DELETE it, not copy it.** `2>/dev/null || echo skip`
  on the check = the step is decorative. Removing it and enforcing exit code is the fix.
- **Don't fabricate an install-time skip for the check.** Tolerate only *setup*
  (installing the tool over a flaky network); never tolerate the *verdict* being skipped.
- **Verify the YAML parses** after editing workflows (PyYAML) and confirm with an
  actual run, not just by eyeballing the diff.
- **Sibling-agent collisions:** in a shared workspace, other agents may edit
  sibling workflow files / manifests in parallel. Restrict your edits to the
  file(s) you own and verify via `git status` that you only touched your own files.
- Always run the surrounding gate (fmt/clippy/test) after touching CI so a config
  change can't land silently on top of a broken build.

## Security-scan / dependency-audit specifics
See `references/cargo-audit.md` for cargo-audit install, JSON confirmation of a
clean tree, RustSec advisory-DB usage to find patched versions, and the
Aliyun-mirror 403 yank-check noise (stderr-only, non-fatal, absent on crates.io).
