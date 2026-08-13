# yolka ↔ rosetta A2A wiring (concrete recipe)

Two sibling Hermes profiles (`yolka` = caller, `rosetta` = research server, both under
`~/.hermes/profiles/`) connected over A2A on the same machine. Verified working
2026-08-10 (Hermes v0.20.0).

## Layout

- **rosetta** = inbound A2A server. Serves `127.0.0.1:9901`, bearer auth.
- **yolka** = outbound caller. Registers rosetta as a peer.
- WebUI session for yolka runs via `tui_gateway/server.py`; **do not** also run yolka's
  messaging gateway (shared `state.db` corruption risk).

## 1. Server side (rosetta)

```bash
export HERMES_HOME=/home/agent/.hermes/profiles/rosetta
hermes plugins enable a2a-platform
hermes config set gateway.platforms.a2a.enabled true
hermes config set gateway.platforms.a2a.extra.port 9901

# Secrets to .env directly (NOT via `hermes config set`):
echo 'A2A_PEER_TOKENS=yolka:34f5...' >> /home/agent/.hermes/profiles/rosetta/.env
echo 'A2A_AGENT_NAME=rosetta'        >> /home/agent/.hermes/profiles/rosetta/.env
```

## 2. Client side (yolka)

```bash
hermes plugins enable a2a-platform
hermes config set a2a_agents.rosetta.url 'http://127.0.0.1:9901'
hermes config set a2a_agents.rosetta.auth.type 'bearer'
hermes config set a2a_agents.rosetta.auth.token '<token>'
hermes config set a2a_agents.rosetta.timeout '120'
```

(The token is inline in yolka's config.yaml here — prefer an env ref for hygiene.)

## 3. Start + verify

```bash
# background server process (pid tracked; rosetta's gateway must stay alive)
HERMES_HOME=/home/agent/.hermes/profiles/rosetta hermes gateway run &

curl -s http://127.0.0.1:9901/.well-known/agent-card.json   # Agent Card, HTTP 200
curl -s -X POST http://127.0.0.1:9901/ -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage",
       "params":{"message":{"messageId":"t1","role":"ROLE_USER",
                 "parts":[{"text":"Reply: pong"}]}}}'
# -> TASK_STATE_COMPLETED, rosetta replied "pong"
```

Multi-turn: reuse the `contextId` from the first reply in later messages. Rosetta's
reply returns under `result.task.status.message`. Audit log:
`~/.hermes/profiles/rosetta/a2a_audit.jsonl` (inbound+outbound, peer keyed).

## 4. Handoff

After the wire works, send the peer a real instruction in the same `contextId`
(proves the channel carries actual communication, not just pings). Rosetta replied:
"Acknowledged — will use A2A on 127.0.0.1:9901 for our communication going forward."

## Quirks hit (see SKILL.md pitfalls for the why)

1. `hermes plugins enable a2a-platform` → toolset NOT added to `platform_toolsets`.
2. `hermes tools enable a2a` → "Unknown toolset" (CLI doesn't load platform plugins);
   gateway loads it fine — rosetta's card advertised the `a2a` toolset.
3. `hermes config set platform_toolsets.cli` can't append a list (scalar coercion only).
4. `hermes config set A2A_PEER_TOKENS ...` → landed in config.yaml, not .env.
5. Current WebUI session never gained native `a2a_*` tools (toolsets fixed at start);
   curl was used instead.
6. The a2a plugin tools import cleanly (`plugins/platforms/a2a/tools.py`), so the
   CLI-discovery gap is a resolver issue, not a broken plugin.
