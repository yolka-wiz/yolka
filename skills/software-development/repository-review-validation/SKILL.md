---
name: repository-review-validation
description: Review unfamiliar repositories and verify release claims.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [repository review, architecture, release validation, smoke testing, security]
---

# Repository Review and Validation

Use this class-level workflow when asked what an unfamiliar repository does, whether its README is accurate, whether a release is usable, or whether a daemon/protocol implementation is wired correctly.

## Workflow

1. **Establish provenance and scope.** Clone into a clean workspace, record the remote, branch/tag, commit, license, language, and repository status. Do not mutate the project while inspecting it.
2. **Read the project’s own contract first.** Inspect README(s), changelog, package manifests, build files, CI workflows, Docker/container files, installers, and example clients. Extract explicit claims about versions, ports, protocols, security, supported platforms, and installation.
3. **Map the executable architecture.** Find entry points and trace startup through configuration loading, listeners/routes, authentication, authorization, core operations, and shutdown. Identify which components are legacy and which are current.
4. **Reconcile documentation with shipped artifacts.** Compare documentation and changelog versions against entry-point version strings, actual listeners, configuration defaults, installer download URLs, firewall rules, container ports, and CI release tags. Report mismatches as operational release risks.
5. **Inspect security boundaries explicitly.** Trace authentication, authorization, path restrictions, command filtering, TLS defaults, origin checks, secret handling, privilege/drop-user behavior, and dangerous operations. Distinguish “implemented” from “enabled by default.”
6. **Run lightweight, real verification.** Use the project’s existing toolchain. Build each major component; run available tests; if it is a daemon or protocol, start it on loopback with a fixture config and exercise the real client against the real server: authentication plus one representative operation per major subsystem. Avoid external hosts and production changes.
7. **Clean up and verify.** Stop temporary processes, remove temporary fixtures, and confirm `git status` is unchanged. Record failed checks accurately, separating environment/setup failures from project failures.
8. **Report evidence, not marketing.** Structure the result as purpose → components → verified behavior → discrepancies → security/release risks → test status. Cite file paths and line numbers where practical. Mark claims not directly verified as `[unverified]`.

## Reusable Reference

See `references/release-consistency-and-smoke-tests.md` for the release-mismatch checklist and a protocol-daemon smoke-test pattern.

## Pitfalls

- A release tag, README, installer, and binary can describe different generations of the same project; never trust the tag alone.
- A successful isolated frame encoder test does not prove the server starts the listener or that the client interoperates; use a real loopback client/server exchange.
- “TLS supported” is not the same as “TLS enabled”; inspect defaults and installer-generated configuration.
- Security modes named `review` or `allowlist` are not protection unless every operation path enforces them, including native RPC/file APIs.
- Benchmark numbers and “production-ready” claims require repository evidence or an executed benchmark; otherwise label them unverified.
- Do not turn missing local binaries or PATH issues into project findings. Use the repository’s documented toolchain path or the environment’s installed equivalent, then report only unresolved project failures.

## Verification Checklist

- [ ] Clean clone and recorded revision
- [ ] README/changelog/manifests/CI/installer compared
- [ ] Entry point and runtime paths traced
- [ ] Authentication and authorization paths checked
- [ ] Build and tests executed
- [ ] Real local smoke test completed where applicable
- [ ] Temporary process/artifacts removed
- [ ] Final repository status verified clean
