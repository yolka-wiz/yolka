---
name: soul-package-authoring
description: "Create ClawSouls-compatible soul packages — author soul.json metadata, SOUL.md identity, IDENTITY.md, AGENTS.md operations, and STYLE.md style guide following the v0.5 spec. Covers progressive disclosure, allowedTools, recommendedSkills, and the full package structure."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [clawsouls, soul, package, persona, spec, v0.5]
    related_skills: [hermes-agent-skill-authoring, plan]
---

# Soul Package Authoring

Author a [ClawSouls](https://github.com/clawsouls/clawsouls) soul package — a structured persona package for SOUL.md-compatible AI agents. Follows the ClawSouls Package Spec v0.5.

## Understanding the ClawSouls Package

A soul package is a directory containing:
- **soul.json** — Package metadata (machine-readable, used for discovery)
- **SOUL.md** — Core identity file (required, loaded into LLM system prompt)
- **IDENTITY.md** — Lightweight identity metadata (optional)
- **AGENTS.md** — Operational instructions (optional)
- **STYLE.md** — Writing style guide (optional)

Spec: https://github.com/clawsouls/clawsouls/blob/main/docs/soul-spec-v0.5.md

## Step 1: Define the Soul's Purpose

Before writing files, define:
- **Who is this agent?** — Role, personality, worldview
- **What can it do?** — Expertise domains and depth
- **How should it behave?** — Boundaries, communication style, safety rules
- **What tools does it need?** — allowedTools, recommendedSkills

## Step 2: Write soul.json

The metadata file for discovery and framework integration. Spec v0.5 fields:

```json
{
  "specVersion": "0.5",
  "name": "kebab-case-name",
  "displayName": "Human Readable Name",
  "version": "1.0.0",
  "description": "One-liner (max 160 chars)",
  "author": {
    "name": "AuthorName",
    "github": "github-handle"
  },
  "license": "MIT",
  "tags": ["tag1", "tag2"],
  "category": "work/category",
  "compatibility": {
    "models": ["*"],
    "frameworks": ["openclaw", "clawdbot", "zeroclaw", "cursor"],
    "minTokenContext": 32000
  },
  "allowedTools": ["browser", "exec", "web_search", "file_read", "file_write"],
  "recommendedSkills": [
    { "name": "skill-name", "version": ">=1.0.0", "required": true },
    { "name": "optional-skill", "required": false }
  ],
  "files": {
    "soul": "SOUL.md",
    "identity": "IDENTITY.md",
    "agents": "AGENTS.md",
    "style": "STYLE.md"
  },
  "disclosure": {
    "summary": "One-line summary (max 200 chars) for quick-scan discovery."
  },
  "deprecated": false,
  "environment": "virtual",
  "interactionMode": "text"
}
```

### Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `specVersion` | Yes | `"0.3"`, `"0.4"`, or `"0.5"` |
| `name` | Yes | Unique kebab-case identifier |
| `displayName` | Yes | Human-readable name |
| `version` | Yes | Semver |
| `description` | Yes | Max 160 chars |
| `author` | Yes | `{ name, github }` |
| `license` | Yes | Permissive only (MIT, Apache-2.0, BSD, CC0, Unlicense) |
| `tags` | Yes | Max 10 |
| `category` | Yes | Category path (e.g. `work/devops`, `creative/writing`) |
| `files.soul` | Yes | Path to SOUL.md (usually `"SOUL.md"`) |
| `allowedTools` | No | Tool transparency signal. Cross-validated by SoulScan. |
| `recommendedSkills` | No | Skills with optional version constraints |
| `disclosure.summary` | No | Level 1 progressive disclosure (max 200 chars) |
| `deprecated` | No | Lifecycle management |
| `environment` | No | `"virtual"` (default), `"embodied"`, `"hybrid"` |

## Step 3: Write SOUL.md

The core identity file loaded into the LLM's system prompt. Structure:

```markdown
# Agent Name - SOUL

## Worldview
Core beliefs, values, principles. Who the agent IS.

## Expertise
Domain table: Domain | Level | Description

## Personality
Temperament, humor, quirks, communication style.

## Boundaries
What the persona refuses or avoids.

## Self-Learning Mechanisms (if applicable)
How the agent improves over time.

## Response Style
Format preferences, structure, conventions.
```

Use a **markdown table** for expertise to keep it scannable:

```markdown
| Domain | Level | Description |
|--------|-------|-------------|
| Python Programming | Expert | 10+ years, async, FastAPI |
| DevOps | Proficient | K8s, Terraform, CI/CD |
```

## Step 4: Write IDENTITY.md (Optional)

Lightweight identity metadata:

```markdown
# Agent Name - Identity

- **Name:** agent-name
- **Emoji:** 🤖
- **Type:** Role description
- **Vibe:** Short personality description
- **Home:** Environment details
- **Workspace:** Working directory
- **Languages:** Spoken/written languages
```

## Step 5: Write AGENTS.md (Optional)

Operational instructions — how the agent behaves in sessions:

```markdown
# Agent Name - Agent Instructions

## Session Behavior
How to start, receive tasks, plan, and delegate.

## Memory Management
What to save to persistent memory, what to skip.

## Tool Usage
Preferred tools for each operation (e.g. use patch over sed).

## Research Protocol (if applicable)
Step-by-step methodology for deep research.

## Domain-Specific Protocols
E.g., network automation protocol, security checklist.

## Error Handling
How to respond to common failure modes.
```

## Step 6: Write STYLE.md (Optional)

Writing style guide:

```markdown
# Agent Name - Style Guide

## Voice
- Direct, first-person
- No hedging
- Appropriate formality

## Structure
1. One-line result at top
2. Summary table for multi-item results
3. Details with code blocks
4. Recommendations

## Code Blocks
- Shell: ```bash
- Python: ```python
- Config: ```text

## Tables
Use for comparisons, before/after, options, benchmarks.

## What to Avoid
Excessive enthusiasm, apologizing, vagueness, over-explaining.
```

## Progressive Disclosure (v0.4+)

| Level | Purpose | Files |
|-------|---------|-------|
| Level 1 — Quick Scan | Discovery, filtering | `soul.json` only |
| Level 2 — Full Read | Active use | `SOUL.md` + `IDENTITY.md` |
| Level 3 — Deep Dive | Extended behavior | `AGENTS.md` + `STYLE.md` |

## Validation Checklist

- [ ] `soul.json` is valid JSON (use `python -m json.tool`)
- [ ] `specVersion` is `"0.3"`, `"0.4"`, or `"0.5"`
- [ ] `name` is kebab-case
- [ ] `description` ≤ 160 chars
- [ ] `disclosure.summary` ≤ 200 chars (if set)
- [ ] `tags` ≤ 10 items
- [ ] `license` is in allowed list (MIT, Apache-2.0, BSD-*, CC0-1.0, Unlicense, ISC)
- [ ] `files.soul` points to an existing file
- [ ] SOUL.md covers: worldview, expertise, personality, boundaries
- [ ] `allowedTools` matches actual tool expectations in SOUL.md/AGENTS.md
- [ ] All referenced files exist in the package directory

## Pitfalls

1. **Kebab-case name only** — The `name` field must be kebab-case (lowercase with hyphens). CamelCase or snake_case is rejected by SoulScan.
2. **Spec version must be >= 0.3** — The registry rejects v0.1 and v0.2. Use `"0.3"`, `"0.4"`, or `"0.5"`.
3. **Copyleft licenses blocked** — GPL, AGPL, LGPL, CC-BY-NC, CC-BY-ND are rejected. Only permissive licenses.
4. **Progressive disclosure mismatch** — If AGENTS.md requires specific tools, declare them in `allowedTools` in soul.json. SoulScan cross-references these.
5. **soul.json vs SOUL.md consistency** — Safety laws in soul.json must also appear as behavioral rules in SOUL.md (dual declaration requirement in v0.5.2 for embodied souls).
6. **SOUL.md loaded into system prompt** — Keep it concise (2-5KB). Token budgets matter. Deep behavior goes in AGENTS.md (Level 3).
