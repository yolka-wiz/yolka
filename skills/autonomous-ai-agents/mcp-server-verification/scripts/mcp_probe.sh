#!/usr/bin/env bash
# mcp_probe.sh — raw MCP protocol probe for any HTTP/SSE MCP endpoint.
#
# Proves the full path WITHOUT an agent restart: initialize handshake,
# Mcp-Session-Id capture, then one real tools/call. Use when
# `hermes mcp test <name>` succeeded but you want evidence that tool
# execution actually works, or when the server isn't wired into Hermes yet.
#
# Usage:
#   MCP_URL="https://mcp.context7.com/mcp" \
#   MCP_TOKEN="<bearer>" \
#   MCP_TOOL="resolve-library-id" \
#   MCP_ARGS='{"libraryName":"HarfBuzz","query":"shape Arabic text"}' \
#   bash mcp_probe.sh
#
# MCP_TOKEN may be omitted; the script then greps the active Hermes profile
# config.yaml for mcp_servers.<name>.headers.Authorization.
set -u
: "${MCP_URL:?set MCP_URL}"
: "${MCP_TOOL:?set MCP_TOOL}"
MCP_ARGS="${MCP_ARGS:-{}}"

if [ -z "${MCP_TOKEN:-}" ]; then
  CFG="${HERMES_HOME:-$HOME/.hermes}/config.yaml"
  MCP_TOKEN=$(grep -A4 "mcp_servers:" "$CFG" 2>/dev/null \
    | grep "Authorization" | head -1 \
    | sed 's/.*Bearer //' | tr -d '"' | tr -d ' ')
fi
if [ -z "$MCP_TOKEN" ]; then
  echo "ERROR: no token — set MCP_TOKEN or configure mcp_servers.<name>.headers.Authorization in $CFG" >&2
  exit 1
fi

# 1) initialize → capture Mcp-Session-Id (lowercase 'mcp-session-id'; may fold lines)
INIT=$(curl -s -i -X POST "$MCP_URL" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mcp-probe","version":"1.0"}}}')

echo "protocol: $(echo "$INIT" | grep -o '"protocolVersion":"[^"]*"' | head -1)"
SESSION=$(echo "$INIT" | grep -i "mcp-session-id:" | head -1 | tr -d '\r' | awk '{print $2}')
if [ -z "$SESSION" ]; then
  echo "ERROR: no Mcp-Session-Id in initialize response; first 300 chars:" >&2
  echo "$INIT" | head -c 300 >&2
  exit 1
fi
echo "session-id: ${SESSION:0:12}..."

# 2) tools/call — one real invocation
RESP=$(curl -s -X POST "$MCP_URL" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$MCP_TOOL\",\"arguments\":$MCP_ARGS}}")

echo "--- tools/call $MCP_TOOL ---"
echo "$RESP" | head -c 600
echo
