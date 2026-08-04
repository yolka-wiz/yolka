# Skills Library — curation manifest

The `skills/` directory is the **complete intended set** for the yolka persona:
hybrid DevOps / network / software engineer with a tech-lead personality.
It is deliberately lean — 113 skills in the old incarnation became this curated
set, dropping the long tail of never-used bundled skills (airtable, comfyui,
p5js, manim-video, touchdesigner, …) and keeping what a working tech lead
actually reaches for.

## Why these skills

### Hermes operating core (must-have)
- `hermes-agent` — hub skill: install, profiles, config, spawning, MCP, security.
  Required to operate and re-provision Hermes itself.
- `hermes-agent-skill-authoring` — author SKILL.md files correctly (the
  self-improvement loop depends on this).
- `plan`, `spike`, `systematic-debugging`, `test-driven-development`,
  `requesting-code-review`, `simplify-code` — the engineering method: plan,
  experiment, debug, test, review, simplify.
- `coding-workflow` — when implementing code for a user request.
- `git-essentials`, `github-pr-workflow`, `github-code-review`, `github-issues`,
  `github-repo-management`, `github-auth`, `codebase-inspection` — every
  engineering task touches git/GitHub.
- `docker-essentials` — containers are table stakes for DevOps.

### DevOps / infrastructure (from the old incarnation — the ones that were used)
- `mirror-discovery` — the most-used old skill (23 uses). Empirical mirror
  probing; valuable real-world knowledge.
- `docker-remote-deployment`, `remote-server-operations`, `server-iac-provisioning`,
  `mesh-vpn-provisioning`, `remote-host-service-inventory`, `agent-workspace-provisioning`,
  `hermes-profile-provisioning`, `hermes-identity-backup` — the ops toolkit.

### Network engineering (from the old incarnation)
- `network-device-management`, `network-inventory-discovery`, `network-config-backup` —
  multi-vendor device work, inventory, backup.

### Software engineering (from the current live profile)
- `codebase-architecture-research` — deep-dive an unknown codebase before changing it.
- `python-debugpy`, `node-inspect-debugger` — remote debugging.
- `security-auditor` — pre-commit security review.
- `inspecting-hermes-desktop-dom` — Hermes desktop internals (for this profile's own UI work).

### Domain: RTL / PDF / documents (the user's current project)
- `open-source-triage` — codebase archaeology for unfamiliar OSS (this is the
  seed of the PDF editor work; keeps the Okular RTL research).
- `persian-rtl-documents` — Persian/Arabic OCR, reshaping, bidi, RTL PDF creation
  (deduplicated in this snapshot).

## Explicitly NOT included (and why)
- The 72 never-used bundled skills (airtable, apple-*, creative/* except where
  relevant, mlops/*, research/paper-writing, …) — dead weight that pollutes the
  skill index and token budget.
- Duplicates: `computer-use` (kept only under autonomous-ai-agents),
  `dogfood` (kept only under software-development), `vllm`/`lm-evaluation-harness`
  near-duplicates (neither kept — not part of this persona's day-to-day).
- Credential-adjacent skills (`credential-manager-provisioning`,
  `server-cleanup-provisioning`) — superseded by secure-by-default practice.

## Layout convention
Skills keep their category directories (`devops/`, `network/`, `github/`,
`software-development/`, `productivity/`, `research/`, `autonomous-ai-agents/`)
matching the Hermes bundled layout so `hermes skills install` / sync behavior
is predictable.

## Adding skills later
The persona's self-improvement loop adds skills as lessons accumulate. When a
new skill is created on a live profile, `build-identity.sh` picks it up
automatically. Keep this manifest updated when the set changes materially.
