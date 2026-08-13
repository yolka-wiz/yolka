---
name: new-stack-onboarding
description: Onboard to an unfamiliar technology stack, framework, language, or toolchain quickly — canonical docs, idioms, toolchain discovery, and a persisted stack note. Use when starting work in a stack you haven't used before, when a project introduces an unknown framework/library/tool, or when the user says "I've never used X".
---

# New Stack Onboarding

Goal: go from "never used this stack" to "productive in it" in one focused pass,
and leave a reusable note so the knowledge sticks.

## When to use

- A task involves a framework, language, or tool you have not worked with before.
- A repo uses an unfamiliar build system, package manager, or runtime.
- The user explicitly asks you to learn something new.

## Procedure

1. **Name the stack precisely.** Language + version, framework + major version,
   build/package tool, target platform. Write it down before searching.

2. **Canonical sources first, in order:**
   - Official docs (not blogs, not AI-generated tutorials) — the "Getting
     Started" page is the contract.
   - Official quickstart template / example repo (e.g. `create-*` scaffolds,
     framework's own example apps).
   - Package registry page (npm/pypi/crates.io/etc.) — check version, maturity,
     maintenance status, license.
   - The stack's own conventions doc (style guide, project layout).

3. **Bootstrap a minimal working example** — never learn by reading only.
   Scaffold the official hello-world, run it, then mutate it: add an error
   path, add a unit test, add logging. This exposes the idioms fast.

4. **Discover and record the toolchain:**
   - Package manager + lockfile convention
   - Linter / formatter / type checker / test runner / debugger
   - Build & run commands (`npm run dev`, `cargo test`, `go test ./...` …)
   - Where config lives and how it's named (clean, conventional naming matters)

5. **Map to what you already know.** Translate: "this is like Flask but with X",
   "this replaces systemd's unit model with Y". Transfer knowledge instead of
   re-learning from zero.

6. **Persist a stack note.** Save a compact note (memory entry or a
   `docs/stack-notes/<stack>.md` in the project) containing: versions, commands,
   idioms, pitfalls, and where to look things up. Future sessions should not
   re-learn what this session discovered.

## Environment adaptation (tools)

Before assuming a tool exists, check the actual environment:

- `which <tool>` / `command -v`, `--version` probes
- `compgen -c | sort -u` to inventory available commands when unsure
- Read the project's own context files first (AGENTS.md, README, Makefile,
  justfile, package.json scripts, docker-compose)
- Respect what's already installed — prefer the environment's existing
  toolchain over installing a parallel one (clean tooling, fewer moving parts)

## Verification

- The hello-world runs end-to-end (build + execute + test).
- You can state the stack's 3 core idioms and 2 common pitfalls unprompted.
- The stack note exists and is accurate.

## Pitfalls

- Don't cargo-cult AI-generated tutorials — verify against official docs.
- Don't install "the recommended" extra tooling before the minimal path works.
- Don't skip the error path — that's where the real idioms live.
