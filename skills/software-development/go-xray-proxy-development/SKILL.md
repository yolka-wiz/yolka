---
name: go-xray-proxy-development
description: "Use when developing Go proxy daemons wrapping xray-core."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [go, xray, proxy, viberayd, viberoxy, socks5, routing, tdd]
    related_skills: [github-pr-workflow, coding-workflow, plan]
---

# Go Xray Proxy Stack Development

Developing the Viberayd/Viberoxy family: Go daemons that fetch proxy
subscriptions, test configs, run a pool of persistent xray WANs, and expose
them behind HTTPS CONNECT + SOCKS5 front-ends with load balancing and
split routing.

## Repo map & delivery mechanics

| Repo | Role | Upstream |
|---|---|---|
| `Viberayd` | subscription aggregator/prober (fetch → test TCP/TLS/protocol/xray → serve `/sub`) | amirrezaalavi/Viberayd |
| `Viberoxy` | proxy server (WAN pool of xray instances, HTTPS CONNECT + SOCKS5, least-connections LB) | amirrezaalavi/Viberoxy |
| `viber-console` | control-plane: supervises both daemons as children, aggregates status (JSON API + Prometheus), schema-driven env-file config editor, single-page SPA (dark/light, mobile-first, zero frontend deps) | own repo `yolka-wiz/viber-console` (not a fork) |

- Work on `yolka-wiz` forks (both exist). Local clone has `origin` = upstream, `fork` = yolka-wiz. Feature branch per change: `feat/<slug>` / `perf/<slug>` / `docs/<slug>` / `chore/<slug>`.
- Before branching: `git fetch origin main && git reset --hard origin/main && git checkout -b <branch>`.
- Push to fork, then `gh pr create -R amirrezaalavi/<repo> --head yolka-wiz:<branch> --base main`.
- Both repos are zero-dependency Go (stdlib only). Viberoxy is flat single-package; Viberayd is layered (`cmd/`, `internal/{daemon,tester,concurrency,cache,orchestrator}`, `pkg/parser`).

## Conventions (both repos)

- **Env-var config, validated at startup.** Bad values = hard error (`fmt.Errorf("error: X=%q: must be a boolean (true/false)")`); out-of-range numerics get clamped with a `slog.Warn` (never silent). Add every new env var to: config struct, `parseConfig`/`LoadConfigFromEnv`, `String()`, README table, AGENTS.md reference, and the defaults test's unset list.
- **Logging:** `slog.Info/Warn/Error` with key-value pairs. Never `log.Println`.
- **Concurrency:** per-slot `sync.Mutex` for state; `sync/atomic` for counters.
- **Tests:** one `*_test.go` per file, in-package (`package main`/`package daemon`), helpers `setenv`/`unsetenv` (with `t.Cleanup` restore), `freePort`, `waitForPort`.
- TDD: failing test first, then minimal implementation. `go build ./...` + `go vet ./...` + full `go test ./...` + `go test -race` on relay/proxy paths before PR.

## Go techniques that work here

- **Variadic signature evolution:** when adding a parameter to a widely-called function (`BuildXrayConfig`, `ApplyResults`), make it variadic (`..., muxEnabled ...bool`) so existing call sites and tests compile unchanged. Default = new behavior; add explicit tests for both new default and old-behavior opt-out.
- **Identical helper in two parallel PRs auto-merges:** adding the same function (e.g. `tuneTCPConn`) on two branches yields identical hunks — git merges them cleanly regardless of order. Say so in the PR body to avoid maintainer worry.
- **Standalone-parse lint noise:** `patch`/`write_file` vet messages like `undefined: Router` when editing one file are standalone-parse artifacts — verify with a real `go test`/`go build`, not the lint field.

## Latency engineering (the mux lesson)

Root cause of "huge routing latency" in this stack: every proxied outbound had
`mux: {enabled: false}` → **each client connection triggered a fresh
TLS/protocol handshake to the upstream proxy server**. Fixes, in impact order:

1. **Enable xray mux** on proxied outbounds (`mux: {enabled: true, concurrency: 8}`) — many client connections share one upstream connection. Never on `freedom` fallbacks. Trade-off: slight per-stream throughput ceiling on huge transfers; keep an env opt-out.
2. **TCP_NODELAY + keepalive(30s)** on both ends of every relayed connection and on the socks5Dial upstream leg — removes Nagle delay on small writes.
3. `domainStrategy` only matters on `freedom`/direct outbounds (`UseIP`). For proxied protocols (vmess/vless/trojan/ss), xray passes the domain to the remote server untouched — no local DNS on that path, don't add settings that don't apply.

## Split routing pattern (geofile-style)

- `RouteMode`: `all-proxy` (default, historical) | `proxy-default` (WAN default, direct list overrides) | `direct-default` (direct default, proxy list overrides).
- Lists: comma env vars + newline files (`#` comments). Suffix semantics: `.example.com` matches domain + subdomains; single-label entry matches exact host only. Case-insensitive; strip trailing dot and `:port`.
- Decision point: **before** `GetLeastLoaded` in CONNECT and SOCKS5 handlers. Direct path = plain `net.Dialer` dial with timeout, tuned socket, access-log `route=direct|wan`, metrics series `{route="direct"}`.
- v1 = TCP routing only; DNS stays client-side. DNS-over-proxy = v2 (needs SOCKS5 UDP ASSOCIATE + xray inbound `udp: true`).

## Pitfalls

- **Probe pre-filters can gate out the real test.** A cheap TCP-connect
  pre-filter before an expensive protocol test (Viberayd's `TCPPing` before
  xray) is a throughput optimization, NOT a correctness gate — on filtered/DPI
  networks a direct TCP connect fails while the same host works fine through
  the proxied test. If the pre-filter marks failures `unreachable` and *skips*
  the authoritative test, the pool can never recover. Fix pattern (shipped
  Viberayd PR #8): env toggle `DAEMON_TCP_PING` (default true preserves the
  fast path; false → skip the pre-filter, test everything, no
  unreachable-marking from the ping stage). General rule: a probe stage should
  be skippable, and its failures should never be the only gate on the real
  test.
- **`net.Pipe` relay benchmarks deadlock** — `net.Pipe` is synchronous; an echo/relay loop with pipes cycles and hangs. Use functional tests with real TCP listeners instead of pipe-based benchmarks.
- **xray UDP/DNS:** Viberoxy SOCKS5 front-end rejects UDP ASSOCIATE with REP 0x07 and xray inbound is `"udp": false` — DNS-over-proxy is real work, not a one-liner.
- **Leak guard:** `IsXraySupported` excludes hysteria2/tuic/wireguard because `buildOutbound` maps them to `freedom` = direct egress = traffic leak. Never promote them without a real outbound.
- **F-string trap in execute_code:** sed/awk commands containing `}` inside an f-string raise `SyntaxError: f-string: single '}' is not allowed`. Use `%`-formatting or a plain string for such commands.
- **Config editor apply-safety:** settings form must show the daemon's *effective* config — file values, else schema defaults — never the console's own process env (`Values()` bug, fixed 2026-08-13). Full URL-replace-by-diff, validation, embed/FileServer gotchas: see `references/viber-console-backend.md`.

## Verification checklist (before declaring done)

1. `go build ./...` and `go vet ./...` clean.
2. Full `go test ./...` green; `go test -race` on relay/proxy paths.
3. New env vars covered by parse tests (default + override + invalid).
4. README env table + AGENTS.md entry points updated.
5. Live end-to-end latency numbers need a real xray + subscription — say so when config-level behavior is what's actually verified.

## References

- `references/xray-config-facts.md` — xray outbound/inbound config facts (mux, domainStrategy, socks, geosite)
- `references/viber-features-v1.md` — concrete v1 feature recipes (latency threshold, mux, split routing) + pending roadmap
- `references/post-merge-conflict-verification.md` — verify a maintainer's merge after overlapping PRs (botched-resolution signatures, reconstruction-diff method, repair pattern)
- `references/viber-console-backend.md` — viber-console backend patterns: stdlib Prometheus text parser, percentile estimation, poll-store design, mock-daemon smoke test
