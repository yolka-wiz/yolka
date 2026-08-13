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

## SRE / cloud / sysadmin expansion (2026-08-13)
Sourced from ClawHub, skills.sh (Trail of Bits), GitHub (antonbabenko, keep-the-why),
plus two custom-authored skills. Goal: full SRE/cloud coverage + engineering mindset.
- `sysadmin` (ClawHub; manual install — blocked by skills-guard keyword scan, content
  manually reviewed, benign best-practice text) — users, processes, storage, maintenance.
- `systemd` (ClawHub) — systemd reference for sysops.
- `k8s` (ClawHub) — kubectl operations against any cluster (kubeconfig-based).
- `terraform-skill` (antonbabenko/terraform-skill, Apache-2.0) — Terraform/OpenTofu
  diagnose-first workflow + 8 reference files. Preferred over ClawHub's vendor-locked
  `oo-terraform` (OOMOL connector — rejected).
- `ansible` (ClawHub) — server provisioning, config management, orchestration.
- `observability` (ClawHub) — metrics/logs/traces mental model, instrumentation budget.
- `incident` (ClawHub) — detect/triage/mitigate/communicate during outages.
- `postmortems` (ClawHub) — deep blameless postmortem workflow.
- `backup` (ClawHub; manual install) — 3-2-1 rule, tested restores, ransomware protection.
- `differential-review` (Trail of Bits via skills.sh) — security-focused diff review.
- `architecture-decision-record-drafter` (ClawHub) — MADR-style ADRs under docs/adr/.
- `ai-tech-lead` (ClawHub) — 4-phase Research→Design→Planning→Code methodology
  (frontmatter added post-fetch; source had none).
- `keep-the-why` (oliver-zehentleitner/keep-the-why, MIT) — preserve decision
  rationale/workarounds the code can't explain; continuous capture + recovery modes.
- `new-stack-onboarding` (custom) — systematic onboarding to unfamiliar stacks:
  canonical docs → hello-world → idioms → persisted stack note; environment-first
  tool discovery.
- `cs-fundamentals` (custom) — compact CS basics reference: complexity, data
  structures, OS, concurrency, networking, databases, systems design.

Rejected after review: `oo-terraform` (vendor-locked to OOMOL), ClawHub `computer-science`
(a tutoring skill, not an agent knowledge base — replaced by custom `cs-fundamentals`),
`observability` skills.sh variant (ClawHub version chosen), persona-heavy skills with
no procedure.

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
