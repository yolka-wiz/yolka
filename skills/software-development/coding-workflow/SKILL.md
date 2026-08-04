---
name: coding-workflow
description: Use when implementing code for a user request. Provides the plan -> execute -> verify -> deliver workflow for clean software development, with user-controlled execution and preference memory.
version: 1.0.4
author: ported from ClawHub (ivangdavila), self-contained rewrite
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coding, workflow, planning, verification, testing]
    related_skills: [plan, test-driven-development, requesting-code-review]
---

# Coding Workflow

Clean-software workflow for code implementation requests: plan, execute, verify, deliver. Adapted from the ClawHub `code` skill.

## When to Use

- User explicitly requests code implementation or a fix
- User asks you to build, modify, or refactor something in a codebase
- Any task where the deliverable is working, tested code

## Workflow

```
Request -> Plan -> Execute -> Verify -> Deliver
```

### 1. Check Memory First

- Read your memory (user preferences) and any `~/code/memory.md` the user has asked you to keep, before planning.
- If the user says "remember I prefer X" or "never do Y again", save it to memory or `~/code/memory.md` (only what they explicitly ask to save).

### 2. Plan Before Code

- Break the request into independently testable steps.
- For anything non-trivial, write the plan with the todo tool and track status as you go.
- Each step must be verifiable on its own (a test, a build, a run, a screenshot).

### 3. Execute

- User controls execution: confirm before destructive or high-impact actions (deletes, force pushes, mass rewrites).
- Sub-agent delegation requires the user's explicit request or a clear parallelizable subtask.
- Keep changes minimal and scoped to the request.

### 4. Verify Everything

| After | Do |
|-------|-----|
| Each function | Run its tests |
| UI changes | Take a screenshot or render check |
| Before delivery | Run the full test suite and build |

### 5. Deliver

- Summarize what was built, how it was verified, and any decisions made.
- Point to the changed files and how to run/use the result.

## Common Traps

- **Delivering untested code** -> always verify first
- **Huge PRs** -> break into testable chunks
- **Ignoring preferences** -> check memory first

## Scope

This skill provides workflow guidance only:

- NEVER executes code automatically without the user's request
- NEVER makes network requests on its own
- NEVER accesses files outside the user's project
- NEVER modifies its own SKILL.md
