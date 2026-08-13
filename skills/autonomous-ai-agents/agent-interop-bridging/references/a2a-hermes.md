# A2A (Agent-to-Agent) on Hermes — verified enable mechanics

Verified against the local source (`plugins/platforms/a2a/`), the plugin's own
README, and the plugin registry — Hermes Agent v0.20.0. **End-to-end peer
conversation was NOT exercised in the session that produced these notes**
(enable-only; the user chose to stop before running the setup). Treat the enable
mechanics below as verified; treat "how a conversation behaves in practice" as
untested until you round-trip one.

## What it is
Open A2A protocol v1.0 (Linux Foundation). Bidirectional:
- **Outbound**: agent calls other A2A agents as tools (toolset `a2a`).
- **Inbound**: Hermes serves an Agent Card + JSON-RPC endpoint so peers can send
  tasks into the *live* gateway session (same agent/memory/tools).

Interoperates with any A2A-compliant peer (another Hermes, LangChain, CrewAI,
Google ADK, OpenClaw). Stdlib-only transport — no `a2a-sdk` dependency.

## Outbound tools (toolset `a2a`)
- `a2a_discover(url)` — fetch + summarize a peer's Agent Card
- `a2a_call(agent, message, context_id?)` — send a task, get reply; multi-turn via `context_id`
- `a2a_list()` — configured peers, saved conversations, metrics
- `a2a_history(context_id)` — recall a persisted A2A conversation
- `a2a_orchestrate(capability, message, mode?)` — fan-out to peers advertising a capability (`all`/`first`/`best`)

## Enable sequence (yolka side, verified)

```bash
hermes plugins enable a2a-platform   # bundled platform plugin; "takes effect on next session"
# the `a2a` toolset becomes known ONLY after the plugin loads (new session).
# Running `hermes tools enable a2a` immediately after → "Unknown toolset 'a2a'".
```
- `hermes plugins list` → row `a2a-platform` shows `not enabled` until enabled.
- Plugin enable state is NOT stored in `config.yaml`; check the plugin registry,
  not `grep config`.
- The inbound platform and outbound toolset are both registered by the plugin's
  `register()`; enabling the plugin gives the outbound tools without exposing an
  inbound server (inbound binds only when the gateway runs it).
- Current running session (e.g. WebUI) will NOT see `a2a_*` tools until a new
  session starts — toolsets load at session start.

## Peer config (outbound → who to call)
In the caller's `config.yaml`:

```yaml
a2a_agents:
  rosetta:
    url: "http://127.0.0.1:9901"
    auth: { type: bearer, token: "<secret>" }   # keep token in .env, reference via env
    timeout: 120
    capabilities: [research]
```
Direct URLs also work — `a2a_call` accepts any A2A endpoint.

## Inbound config (peer's side — rosetta, to be callable)
Rosetta profile config + env:
```yaml
gateway:
  platforms:
    a2a:
      enabled: true
      extra:
        port: 9901
```
Env (in the peer's `.env`): `A2A_PORT` (default 9900; pick non-colliding),
`A2A_PEER_TOKENS="yolka:<token>"` (per-peer, preferred) or `A2A_BEARER_TOKEN`.
Then the peer's gateway must be RUNNING: `hermes -p rosetta gateway run` (background).
No server running ⇒ outbound calls from me fail even with tools loaded.

## Server surfaces (verified from source)
- Agent Card: `GET /.well-known/agent-card.json` (canonical v1.0; legacy `agent.json` also answers)
- JSON-RPC 2.0: `POST /` (v1.0 methods + pre-1.0 path-style aliases)
- SSE streaming for `SendStreamingMessage`; push notifications (webhooks) HMAC-SHA256 signed
- Inbound tasks injected into the live gateway session; keyed by `contextId`

## Security model (verified from source)
- No bearer token ⇒ binds `127.0.0.1` only; refuses to widen without token + `A2A_HOST`
- Per-peer tokens (`A2A_PEER_TOKENS`) drive identity / rate-limit / audit
- Inbound text prompt-injection filtered, framed as untrusted peer input; remote
  peers can't run operator slash commands
- Outbound replies scrubbed of credential-shaped strings
- Audit log `~/.hermes/a2a_audit.jsonl`; conversations persist to
  `~/.hermes/a2a_conversations/` (survive compaction/restarts)
- Anti-loop per-context turn cap (`A2A_MAX_PINGPONG_TURNS`, default 5, max 20)

## Env vars (abridged)
| Var | Default | Meaning |
|---|---|---|
| `A2A_PEER_TOKENS` | unset | per-peer `name:token,…` (preferred) |
| `A2A_BEARER_TOKEN` | unset | shared token; identity falls back to caller IP |
| `A2A_HOST` | 127.0.0.1 | bind host; only widens with a token set |
| `A2A_PORT` | 9900 | inbound port |
| `A2A_AGENT_NAME` | hostname-derived | name on Agent Card |
| `A2A_PUBLIC_URL` | unset | routable URL advertised (reverse proxy/k8s) |
| `A2A_TRUSTED_PEERS` | unset | allow-list of authenticated identities |
| `A2A_ALLOW_ALL_USERS` | false | allow any authed peer (dev only) |
| `A2A_RATE_LIMIT` | 60 | requests/min per identity |
| `A2A_REPLY_TIMEOUT` | 300 | secs to wait for agent reply |

## Decision guidance (when A2A vs lighter)
See the umbrella SKILL.md decision matrix. Key: for **same-machine Hermes
profiles**, the docs steer toward delegation/kanban; use A2A only when the peer's
separate profile/context is genuinely the point. For the agno fleet, MCP is
lighter than A2A.
