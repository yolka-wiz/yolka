---
name: remote-agent-security-auditing
description: Use when auditing AI-agent remote execution systems.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, remote-execution, AI-agents, protocol, infrastructure]
    related_skills: [security-auditor, codebase-architecture-research, requesting-code-review]
---

# Remote Agent Security Auditing

## When to Use

Use when reviewing an AI-agent remote execution daemon, control protocol, SDK, installer, container, or deployment claim that can execute commands, allocate PTYs, access files, or manage infrastructure.

Audit systems that give an AI agent remote shell, PTY, filesystem, process, or infrastructure-control capabilities. The core question is not whether the protocol works; it is whether every dangerous capability is authenticated, authorized, bounded, observable, and safely deployed.

## Workflow

1. **Map the repository before judging claims.** Identify daemon/server, wire protocol, client SDK, policy/configuration, installer/service/container, CI/release, examples, and documentation. Record the default ports, protocols, privilege model, credential sources, and trust boundaries.
2. **Split the review into independent surfaces.** Run parallel workstreams for: (a) wire/server/PTY/native operations; (b) authentication, authorization, policy, installer, and deployment; (c) SDK, release artifacts, CI, and advertised claims. Give each a non-overlapping file set and require exact `file:line` evidence.
3. **Require durable navigation guides.** Each workstream writes a guide under `docs/security-audit/` covering every major directory/file it reviewed, data flow, trust boundaries, protocol compatibility, and verified checks. Add an index linking the guides. Read the files back and verify them; a subagent's self-report is not proof.
4. **Trace every dangerous capability end to end.** For each opcode/API, follow the call path from network input to command execution, PTY input, file read/write/delete, process creation, or system information. Confirm separately that authentication, operation authorization, path containment, quotas, and privilege separation apply. Do not assume a legacy `exec` allowlist protects newer PTY or native RPC paths.
5. **Audit the deployment path without executing untrusted installers.** Inspect shell installers, Dockerfiles, systemd units, release workflows, and examples for default credentials, plaintext transport, mutable downloads, absent checksums/signatures, root execution, missing sandboxing, exposed ports, unsafe firewall changes, and version/port drift. Never run a remote installer or connect to a deployed node during source review.
6. **Validate functionality independently.** Run safe local checks appropriate to the stack: build, vet/static checks, race-instrumented tests, language compilation, shell syntax validation, and a loopback protocol smoke test. Record an empty test suite as a finding. Passing compilation validates mechanics, not authorization or safety.
7. **Rank by exploit path and preconditions.** A bearer-token remote shell with arbitrary file write/delete is critical when reachable, especially as root. Plaintext token transport, autonomous default mode, unsigned artifact installation, missing sandboxing, origin allow-all, and resource exhaustion are normally high. Mark performance and security claims unverified when no reproducible tests or measurements exist.
8. **Handle worker failure explicitly.** If a subagent collects evidence but stalls before writing or returning, stop it, reconstruct the guide from verified source, and state what was independently verified. Never claim a worker produced an artifact that was not read back.

## Required report shape

- Executive verdict: safe, unsafe, or conditional, with deployment assumptions.
- Architecture and trust-boundary map.
- Severity table: severity, finding, exploit preconditions, evidence, impact, fix, confidence.
- Separate confirmed findings from hypotheses and unverified marketing claims.
- Reliability findings: tests, limits, error handling, version drift, backpressure, observability.
- Remediation order: containment first, then authorization, transport, privilege, resource limits, tests, and release hygiene.
- Self-critique: SPOFs, missing backups/recovery, bootstrapping hazards, version drift, complexity/value trade-offs, and what the audit did not verify.

## Pitfalls

- Do not equate token authentication with authorization.
- Do not review only the documented/legacy API; newer opcodes often bypass policy code.
- Do not call a plaintext optional-TLS deployment “TLS-secured.” Check every listener.
- Do not trust default deny lists for shell safety; shell syntax, interpreters, symlinks, and alternate binaries defeat string filters.
- Do not execute `curl | bash`, install services, alter firewalls, or probe real targets as part of source review.
- Do not report benchmark numbers without a benchmark harness and environment details.

## Support files

- `references/remote-agent-audit.md` — evidence checklist, finding template, and safe verification probes.
