---
name: agent-interop-bridging
description: "Use when bridging Hermes agents to other agents."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, a2a, agent-to-agent, kanban, mcp, delegation, multi-agent, interop]
---

# Agent-to-Agent Interop Bridging

How to connect agents to each other (yolka ↔ rosetta profile, yolka ↔ agno fleet,
or any cross-framework link) on one machine or across machines — and which
mechanism to choose. This is the **decision layer**; the specific protocol
mechanics live in `references/`.

## When to use

- User asks to "talk to / connect / bridge" another agent (a second Hermes
  profile, an agno fleet, a LangChain/CrewAI/ADK agent, OpenClaw, etc.).
- You need one agent to call another and get a reply back in your own thread.
- Choosing between the many ways to do it and avoiding over-engineering.

## Decision matrix — pick the LIGHTEST that meets the goal

For this user, **lightweight-first** is a hard preference: benchmark/verify
before choosing, and stop when a task drags. Present this table, recommend the
lightest fit, and DO NOT start heavy wiring until the user picks.

| Goal | Lightest fit | Weight | When |
|---|---|---|---|
| Offload work, keep it inside yolka | `delegate_task` (in-process subagents) | very low | You don't need the *other* agent's separate model/memory/context |
| Durable task queue to another Hermes profile (no live chat) | **kanban** (`hermes kanban`) | low | Hermes-native, same machine, no network/ports/tokens. Docs' recommended choice for same-machine profiles |
| yolka → agno fleet (tool calling) | **MCP** | low | agno already ships FastAPI + native MCP support; expose the fleet as an MCP server |
| yolka → rosetta, LIVE call into rosetta's own model+memory | **A2A** | medium (server process + token + port) | The Hermes-native inter-profile protocol. There is NO in-process way to reach another profile's context |
| Fire-and-forget one-shot into another profile | `hermes -p <profile> chat -q` subprocess | lowest | ...but that's the terminal path users often want to avoid |

### The critical reframe (verified this session)
A2A exists to cross **process/machine/framework** boundaries. On a **single
container**, that boundary is thin — so A2A (HTTP server, bearer token, port,
JSON-RPC) is overkill for most cases. BUT for a **live call into another Hermes
profile's own context specifically**, A2A is genuinely the *lightest* Hermes-native
option, because `delegate_task` spawns children of the *current* profile and cannot
reach a sibling profile's memory/model. Don't dismiss A2A as "heavyweight" when the
specific hop genuinely needs it — it is the native tool.

## Workflow (for this user)

1. **Propose, don't execute.** Lay out the decision matrix and recommend the
   lightest fit. When wiring touches multiple profiles, starts servers, or sets
   tokens, ask which path the user wants FIRST.
2. **Wait for an explicit pick.** The user will say "stop, I will choose" rather
   than let you run a heavy setup they're unsure about. Stop immediately, hold
   state, and present the current exact state so they can decide.
3. **Report state precisely before running anything.** Say what's already done
   (e.g. "only `hermes plugins enable a2a-platform` — reversible, nothing started")
   and what is NOT done (servers, tokens, peer config, gateway).
4. **Verify before declaring done.** A2A peer reachability = fetch the peer's
   Agent Card (`a2a_discover`) and actually round-trip a task, not "configured."

## Pitfalls (all hit or confirmed this session)

- **`hermes tools enable a2a` → "Unknown toolset 'a2a'"** until the plugin is
  loaded. Plugin enable says "takes effect on next session" — a CLI subprocess run
  *right after* enabling does NOT yet see the toolset. The `a2a` toolset only
  appears in sessions after the plugin loads.
- **A2A plugin enable state is NOT written to `config.yaml`.** It lives in an
  enabled/disabled plugin set (see `hermes plugins list`), and the toolset-attach
  helper (`_toggle_plugin_toolset`) only fires when the plugin exposes a recognized
  toolset key. Check `hermes plugins list` / `hermes tools list`, not `grep config`.
- **This session's running WebUI won't get new tools mid-session.** Toolsets load
  at session start; enabling A2A means a NEW session before `a2a_*` tools exist.
- **Inbound A2A requires the peer to be a live server** (its gateway running with
  the platform bound to a port + token). Client tools alone can't call a peer that
  isn't serving.
- **Same-machine**: docs explicitly steer same-machine profiles toward
  delegation/kanban over A2A. Only use A2A when the separate context is the point.
- **Tokens in config, not committed**: peer `auth` tokens belong in `.env`
  (secrets), referenced via env, never in a repo or memory file.

## Related / overlap note
`mcp-server-verification` overlaps on the MCP row of the decision matrix (use it
when you actually stand up an MCP bridge). The agno skills (`agno-agent-*`) cover
building the fleet; this skill covers bridging *to* it.

See `references/a2a-hermes.md` for the verified A2A enable mechanics and config.
