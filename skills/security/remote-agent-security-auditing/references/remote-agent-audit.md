# Remote Agent Audit Reference

## Evidence checklist

- Record commit, repository tree, default branches/tags, and exact file/line references.
- Map every listener, protocol version, port, authentication step, and post-auth capability.
- Trace each dangerous operation: shell/PTY, process spawn, file read/write/delete, stream/tail, sysinfo, admin/config changes.
- For every operation, verify authentication, authorization, path containment, privilege, resource limits, logging, deadlines, and cleanup.
- Inspect defaults and deployment artifacts: TLS, tokens, user/group, systemd sandboxing, container user/capabilities, firewall, downloads, checksums/signatures, version/port consistency.
- Search for bypasses: legacy versus new APIs, alternate opcodes, direct syscall handlers, symlinks, path prefix checks, shell parsing, and mode-specific branches.
- Separate confirmed source findings, runtime-confirmed behavior, hypotheses, and unverified product claims.

## Safe verification probes

Use only local fixtures or loopback services owned by the audit:

```text
build -> vet/static check -> race-instrumented tests -> language compile
shell syntax validation -> start with test config on loopback
client authentication -> harmless sysinfo/stat -> bounded PTY smoke test -> cleanup
```

Never execute a remote installer, pipe mutable remote content into a shell, mutate system services/firewalls, or connect to a real deployment as part of source review.

## Finding template

```markdown
### [Severity] Short title

- **Precondition:** What an attacker must control or obtain.
- **Evidence:** `path/to/file.ext:line-line` and the relevant call path.
- **Impact:** Confidentiality, integrity, availability, and privilege consequences.
- **Confidence:** Confirmed source / runtime-confirmed / hypothesis.
- **Fix:** Smallest safe remediation, followed by defense-in-depth.
- **Verification gap:** Missing test, benchmark, or deployment proof.
```

## Parallel-worker contract

Give each worker a non-overlapping surface and a unique guide path under `docs/security-audit/`. Require exact citations and a structured result. After completion, independently verify the guide exists and read it back. If a worker stalls after collecting evidence, stop it and finish the guide from verified source; do not report an unreturned claim as fact.
