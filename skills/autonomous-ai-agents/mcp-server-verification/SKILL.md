---
name: mcp-server-verification
description: "Verify MCP server connectivity (hermes mcp test + probe)."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [MCP, context7, verification, protocol, curl, hermes]
    related_skills: [hermes-agent]
---

# MCP Server Verification

Prove an MCP endpoint works end-to-end — connection, auth, tool discovery,
AND a real tool call — without waiting for an agent restart.
Use when the user says "check <X> connection", "try the mcp server", or when
MCP tools are configured but you suspect the server/auth/endpoint.

## When to Use

- "check context7 connection and try mcp server" (or any MCP provider)
- After wiring `mcp_servers` in Hermes config, before declaring it done
- Debugging "Failed to connect to MCP server" / tools not appearing

## Method

1. **See what's configured** — `hermes mcp list`. If the server is missing,
   wire it (see hermes-agent skill, `references/native-mcp.md`):
   ```bash
   hermes config set mcp_servers.<name>.url "<endpoint>"
   hermes config set mcp_servers.<name>.headers.Authorization "Bearer <key>"
   ```
   Never hand-edit config.yaml. `hermes mcp add <name> --url ... --auth header`
   also works.
2. **Hermes-native test** — `hermes mcp test <name>`: connects, runs tool
   discovery, lists discovered tools. Passing = transport + auth + discovery OK.
3. **Raw protocol probe** (proves tool calls actually execute) — run
   `scripts/mcp_probe.sh` with `MCP_URL` / `MCP_TOKEN` / `MCP_TOOL` / `MCP_ARGS`:
   initialize → capture `Mcp-Session-Id` header → `tools/call` → print result.
   This is the immediate proof even though the agent cannot hot-load the tool
   mid-session.
4. **Restart caveat** — MCP tools load at agent startup; no hot reload. Tell
   the user tools appear as `mcp_<server>_*` after the next restart. The probe
   is the immediate proof; the restart is only for in-session availability.

## Pitfalls

- **SSE session header**: SSE/streamable-HTTP endpoints return
  `Mcp-Session-Id` in the initialize response. Header name is lowercase
  `mcp-session-id`; it can fold across lines — parse carefully. Every
  subsequent request must carry it.
- **Strict args validation**: `tools/call` rejects wrong argument names with
  `-32602` and the expected path in the error (e.g. `resolve-library-id` needs
  BOTH `libraryName` AND `query`; wrong key → error tells you the right one).
- **Never echo the token**: read it from the profile config or env; keep it
  out of visible output (Hermes redacts it, but don't print it yourself).
- **Bearer in config.yaml is expected**: `Authorization` under
  `mcp_servers.<name>.headers` is the documented pattern. Keys belong in the
  profile config, NOT in repos (a committed key in a public repo must be
  rotated).
- **Discovery ≠ authorization**: `hermes mcp test` succeeding proves
  discovery; a real `tools/call` proves the key is authorized. Do both.

## Verified example

context7 (2026-08-05): `hermes mcp test context7` → Connected (4294ms),
2 tools (resolve-library-id, query-docs). Raw probe: initialize OK
(protocolVersion 2024-11-05), `resolve-library-id("HarfBuzz","shape Arabic
text")` → `/harfbuzz/harfbuzz`; `query-docs(/harfbuzz/harfbuzz, cluster_level)`
→ `hb_buffer_set_cluster_level` API text.

## Support files

- `scripts/mcp_probe.sh` — raw MCP protocol probe (initialize → tools/call)
  for any HTTP MCP endpoint.
