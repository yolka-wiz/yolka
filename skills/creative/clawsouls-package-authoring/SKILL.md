---
name: clawsouls-package-authoring
description: "Create ClawSouls-compatible agent persona packages (soul.json, SOUL.md, IDENTITY.md, AGENTS.md, STYLE.md) following spec v0.5. Progressive disclosure, multi-framework compatibility, lifecycle management."
version: 1.0.0
author: Hermes Agent
platforms: [linux, macos, windows]
---

# ClawSouls Package Authoring

Use this skill when the user asks you to:
- Create a ClawSouls-compatible agent persona ("soul")
- Write a SOUL.md for an agent
- Package an agent identity for OpenClaw, Clawdbot, ZeroClaw, Cursor, or Hermes
- Follow the ClawSouls soul-spec format

## Spec Reference

The authoritative spec lives at: https://github.com/clawsouls/clawsouls/tree/main/docs

Latest version: **v0.5** (`soul-spec-v0.5.md`)

## Package Files

| File | Required | Purpose | Load Level |
|------|----------|---------|------------|
| `soul.json` | Yes | Package metadata — name, version, tags, compatibility, allowed tools, declaration | Level 1 — Quick Scan |
| `SOUL.md` | Yes | Core identity — worldview, expertise, personality, boundaries, self-learning | Level 2 — Full Read |
| `IDENTITY.md` | No | Lightweight metadata — name, emoji, type, vibe, languages | Level 2 — Full Read |
| `AGENTS.md` | No | Operational instructions — session behavior, memory management, tool usage, protocols | Level 3 — Deep Dive |
| `STYLE.md` | No | Writing style — voice, structure, language-specific rules, code block conventions | Level 3 — Deep Dive |
| `HEARTBEAT.md` | No | Periodic background task configuration | Level 3 — Deep Dive |
| `examples/` | No | Calibration material (good-outputs.md, bad-outputs.md) | Level 3 — Deep Dive |

## soul.json Fields (v0.5)

### Required

| Field | Type | Example |
|-------|------|---------|
| `specVersion` | string | `"0.5"` |
| `name` | string (kebab-case) | `"senior-devops-engineer"` |
| `displayName` | string | `"Senior DevOps Engineer"` |
| `version` | semver | `"1.0.0"` |
| `description` | string (max 160 chars) | `"Infrastructure automation and monitoring expert."` |
| `author` | object | `{ "name": "...", "github": "..." }` |
| `license` | string (SPDX) | `"MIT"`, `"Apache-2.0"`, `"CC0-1.0"` |
| `tags` | string[] (max 10) | `["devops", "networking", "linux"]` |
| `category` | string | `"work/devops"` |
| `files.soul` | string | `"SOUL.md"` |

### Key Optional Fields

| Field | Type | Purpose |
|-------|------|---------|
| `compatibility.frameworks` | string[] | `"openclaw"`, `"clawdbot"`, `"zeroclaw"`, `"cursor"`, `"windsurf"`, `"continue"`, `"hermes"` |
| `compatibility.models` | string[] | Glob patterns like `"anthropic/*"`, `"openai/*"` |
| `compatibility.minTokenContext` | number | Minimum context window needed |
| `allowedTools` | string[] | Transparency signal: which tools this soul expects |
| `recommendedSkills` | object[] | `{ name, version?, required? }` |
| `disclosure.summary` | string | One-line for Level 1 quick-scan (max 200 chars) |
| `deprecated` | boolean | Lifecycle flag |
| `supersededBy` | string | Replacement soul `"owner/name"` |
| `environment` | string | `"virtual"` (default), `"embodied"`, `"hybrid"` |
| `interactionMode` | string | `"text"`, `"voice"`, `"multimodal"`, `"gesture"` |
| `files.identity` | string | Path to IDENTITY.md |
| `files.agents` | string | Path to AGENTS.md |
| `files.style` | string | Path to STYLE.md |
| `files.heartbeat` | string | Path to HEARTBEAT.md |
| `files.avatar` | string | Path to avatar image |

### Allowed Licenses (Registry)

Only permissive: `Apache-2.0`, `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `CC-BY-4.0`, `CC0-1.0`, `ISC`, `Unlicense`.

Copyleft and restrictive CC are blocked.

## Progressive Disclosure (3 Levels)

| Level | What to Load | When |
|-------|-------------|------|
| **Level 1 -- Quick Scan** | `soul.json` only (`disclosure.summary`) | Discovery, filtering, marketplace browsing |
| **Level 2 -- Full Read** | `SOUL.md` + `IDENTITY.md` | Agent loads persona for active use |
| **Level 3 -- Deep Dive** | `AGENTS.md`, `STYLE.md`, `HEARTBEAT.md`, `examples/` | Extended behavior, calibration, style |

## SOUL.md Structure

The core identity file. Organize into these sections:

### Worldview
Core beliefs, values, principles. 3-5 bullet statements the agent holds as axioms.

### Expertise
Table format with Domain, Level, Details columns. Cover all knowledge domains, each with a Level (Expert/Proficient/Competent/Novice) and a brief description of what tools or frameworks are used.

### Personality
List of personality traits as concise statements. Calm, methodical, direct, self-improving, etc.

### Boundaries
Hard constraints the agent must not cross. Fabrication, unverified access, data destruction without confirmation, running code it doesn't understand.

### Self-Learning (if applicable)
How the agent improves over time: tool outcome logging, memory consolidation, skill authoring, pattern recognition.

### Response Style
Formatting conventions: summarize first, tables for comparisons, code blocks for commands, RTL handling for Persian/Arabic/Hebrew.

## IDENTITY.md

Lightweight file with:
- **Name:** Both display and ID
- **Emoji:** A character + icon pair
- **Type:** Role classification
- **Vibe:** Mood/tone keywords
- **Home:** Where the agent runs (hostname or IP)
- **Workspace:** Working directory path
- **Languages:** Spoken languages

## AGENTS.md

Operational instructions for the agent. Cover:

- **Session Behavior** — Startup routine, task entry, planning, delegation
- **Memory Management** — What to save vs skip, priority rules
- **Tool Usage** — Preferred tools for each operation (read_file over cat, patch over sed, etc.)
- **Domain-Specific Protocols** — Research protocol, network automation protocol, deployment protocol
- **Error Handling** — How to react to non-zero exits, timeouts, permissions, network errors

## STYLE.md

Writing style guide:

- **Voice** — Direct/hedging, first-person/third-person, formality level
- **Structure** — Output format (one-line result, summary table, details, recommendations)
- **Language-Specific Rules** — Persian/Arabic RTL handling, code-switching
- **Code Blocks** — Language annotations for each block type
- **Tables** — When to use them, formatting rules
- **What to Avoid** — Excessive enthusiasm, apologizing, vague timelines, anthropomorphizing tools

## Writing Persian/RTL Content

When the soul works with Persian or Arabic content:

```python
import arabic_reshaper
from bidi.algorithm import get_display

text = '\u0633\u0644\u0627\u0645 \u062f\u0646\u06cc\u0627'
reshaped = arabic_reshaper.reshape(text)
bidi_text = get_display(reshaped)
```

Always reshaped + bidi before rendering. Use `tesseract -l fas+eng` for bilingual OCR. Noto Arabic fonts are sufficient for most use cases; `fonts-farsiweb` adds Persian-specific web fonts.

## Categorization Convention

Categories use dot-separated path format:
- `work/devops` — DevOps and infrastructure
- `work/document-ops` — Document processing
- `work/research` — Research and analysis
- `work/network` — Network automation
- `creative/writer` — Creative writing
- `creative/artist` — Visual art
- `personal/assistant` — Personal productivity
- `fun/entertainment` — Entertainment

## Hermes Profile Integration

When deploying a soul package into a Hermes profile (local or remote via SSH):

1. **Create the profile first** — `hermes profile create <name>` — and let it finish entirely.
2. **Wait for default file generation** — the create command may sync bundled skills or generate default SOUL.md stubs. Do NOT write custom files during this window.
3. **Write custom files last** — after the profile is confirmed stable (`hermes profile show <name>`), write or scp your SOUL.md, soul.json (into `soul/`), SKILL.md files (into `skills/<name>/`), and config.yaml.
4. **Verify skills are recognized** — run `hermes -p <name> skills list` to confirm all SKILL.md files are parsed and enabled.

Placement in a Hermes profile:
```
~/.hermes/profiles/<name>/
├── config.yaml          # Model, provider, toolsets
├── SOUL.md              # Core identity (Level 2)
├── soul/
│   └── soul.json        # Package metadata (Level 1)
├── skills/
│   ├── skill-one/
│   │   └── SKILL.md
│   └── skill-two/
│       └── SKILL.md
├── .env                 # API keys (generated by profile create)
├── sessions/
├── memories/
└── logs/
```

See `references/engineer-soul-example.md` for a complete working example of a Mechanical & Electrical Engineer profile deployed to a remote server.

## Pitfalls

- **Set specVersion explicitly** — v0.1 and v0.2 are rejected by the registry. Always use v0.3+.
- **`skills` is deprecated in v0.4+** — use `recommendedSkills` array instead. Backward compatible for consumers but new packages should use the new format.
- **`modes` and `interpolation` are deprecated** — no runtime consumes them. Omit entirely in v0.4+.
- **Description max 160 chars** — the registry truncates longer descriptions.
- **Tags max 10** — extra tags are silently dropped.
- **License must be on the allowlist** — copyleft gets rejected at publish.
- **Hermes profile file overwrite** — `hermes profile create` may generate default SOUL.md stubs and skill templates that overwrite files placed before or during the creation window. Always create the profile, wait for it to finish, verify with `hermes profile show`, then write custom files (SOUL.md, soul.json, skills). If custom files appear as stubs after deployment, re-copy them — the profile creation process is the likely culprit, not a failed transfer.
- **KDE desktop cleanup on Debian** — when creating a soul for a server that also has a GUI, reference the `server-cleanup-provisioning` skill for the full phases: stop services, purge GUI packages, autoremove, clean home, and migrate to `/opt/agent`.
- **Sub-agent profile creation may produce empty/stub files** — `delegate_task` sub-agents can create Hermes profiles via `hermes profile create` but the files they write (SOUL.md, config.yaml, skills) may be zero-byte or stubs due to heredoc quoting failures or race conditions with the profile creation process. Always verify after sub-agent completion: check `wc -l SOUL.md`, `cat config.yaml | grep model`, `ls skills/*/SKILL.md`. If SOUL.md is 0 bytes or skills are missing, re-write them directly via scp from the parent session — the `remote-server-operations` skill's write-locally-then-scp pattern handles this reliably.
