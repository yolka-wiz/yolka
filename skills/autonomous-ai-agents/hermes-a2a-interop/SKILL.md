---
name: hermes-a2a-interop
description: "Use when connecting Hermes agents over the A2A protocol."
version: 1.0.0
author: yolka
tags: [hermes, a2a, agent2agent, agent-interop, multi-agent]
platforms: [linux]
---

# Hermes A2A (Agent-to-Agent) Interop

Connect independent Hermes profiles (or Hermes to any A2A-compliant peer) over the
open Agent2Agent protocol v1.0. A2A works **both directions**: your agent calls other
agents as tools (outbound), and other agents send tasks to your Hermes over HTTP
(inbound). Uses only stdlib — no `a2a-sdk` dependency.

Authoritative plugin doc: `~/.hermes/hermes-agent/plugins/platforms/a2a/` (`README.md`,
`DESIGN.md`). A2A protocol spec: https://a2a-protocol.org

## When to use A2A vs. lighter alternatives

A2A crosses **process / machine / framework** boundaries. For Hermes profiles on the
**same machine**, prefer lighter tools first:

| Need | Lighter option | A2A justified when |
|---|---|---|
| Offload work, stay in one agent | `delegate_task` (in-process subagents) | — |
| Durable multi-profile task queue | `hermes kanban` | — |
| Live call INTO another profile's own model+memory | — | **A2A is the native fit** (delegate_task only spawns children of the current profile) |
| Call an agno/LangChain/CrewAI agent | **MCP** (they expose it natively) | peer only speaks A2A |

`delegate_task` cannot reach another profile's memory/model — it spawns the current
profile's own children. A2A is the lightest native way to bridge two Hermes profiles'
contexts. For an existing agno fleet, prefer MCP over A2A.

## Enable (both sides)

```bash
# Server side (the agent that answers calls):
hermes plugins enable a2a-platform
hermes config set gateway.platforms.a2a.enabled true
hermes config set gateway.platforms.a2a.extra.port 9901
# client side (the agent that makes calls): just the plugin + a peer entry

# Secrets go in .env — NOT via `hermes config set` (see pitfalls):
#   echo 'A2A_PEER_TOKENS=<peerName>:<token>' >> <profile>/.env
#   echo 'A2A_AGENT_NAME=<name>' >> <profile>/.env
```

Server-side env vars (read by the adapter): `A2A_PEER_TOKENS` (per-peer, preferred),
`A2A_BEARER_TOKEN` (shared), `A2A_HOST` (127.0.0.1 default; only widens with a token),
`A2A_PORT` (9900 default), `A2A_AGENT_NAME`, `A2A_PUBLIC_URL`, `A2A_MAX_PINGPONG_TURNS`
(anti-loop, max 20), `A2A_REPLY_TIMEOUT` (default 300s).

## Configure the peer (outbound side)

```yaml
a2a_agents:
  rosetta:
    url: "http://127.0.0.1:9901"
    auth: { type: bearer, token: "<secret>" }
    timeout: 120
    capabilities: [research]
```

## Start the server and verify

```bash
# Run the server profile's gateway in the background (long-lived):
HERMES_HOME=<profile> hermes gateway run &

# Verify — fetch the Agent Card, then send a real JSON-RPC task:
curl -s http://127.0.0.1:9901/.well-known/agent-card.json
curl -s -X POST http://127.0.0.1:9901/ -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage",
  "params":{"message":{"messageId":"t1","role":"ROLE_USER","parts":[{"text":"Reply: pong"}]}}}'
```

Multi-turn: pass the same `contextId` in each message; the peer's reply comes back
`TASK_STATE_COMPLETED` with `status.message`. Every exchange is audit-logged to the
server profile's `a2a_audit.jsonl` (both inbound and outbound, keyed by peer identity).

## Pitfalls (learned the hard way)

- **`hermes plugins enable a2a-platform` does NOT attach the toolset** to
  `platform_toolsets` — that only happens on the dashboard enable path. The plugin
  enables (appears "enabled" in `hermes plugins list`) but the outbound tools may not
  surface. Verify separately.
- **`hermes tools enable a2a` can fail "Unknown toolset"** in the CLI context because
  platform-kind plugins aren't loaded by the tools CLI's plugin discovery. This is
  CLI-specific — the **gateway loads the toolset fine** (the server's own Agent Card
  advertised the `a2a` toolset). Don't rabbit-hole on the CLI failure.
- **`hermes config set` does not parse list values** — scalar coercion to
  bool/int/float only. You cannot append to a list (e.g. `platform_toolsets.cli`) with
  it.
- **`hermes config set A2A_PEER_TOKENS ...` routes to config.yaml as a custom key, NOT
  .env.** Env-routing only covers recognized keys. Write `A2A_*` secrets directly to
  the profile's `.env` file.
- **WebUI/TUI session toolsets resolve from `platform_toolsets.cli`** (via
  `_get_platform_tools(cfg, "cli")`), and **toolsets are fixed at session start** — a
  current session never gains native `a2a_*` tools mid-flight; restart required.
- **Don't run a second gateway for a profile that has a live WebUI/tui session** — they
  share `state.db`; concurrent access risks corruption.
- **Secret hygiene:** keep peer tokens in `.env` (`A2A_PEER_TOKENS`), not inline in
  `config.yaml`. Yolka's inline peer `auth.token` was a smell; prefer an env ref.
- **Prioritize the wire over the toolset.** Get the server up and prove it with `curl`
  first; the native-toolset wiring is a follow-up convenience, not the deliverable.

## Reference

- `references/yolka-rosetta-setup.md` — concrete two-profile (yolka↔rosetta) wiring
  recipe with exact commands and the quirks hit.
