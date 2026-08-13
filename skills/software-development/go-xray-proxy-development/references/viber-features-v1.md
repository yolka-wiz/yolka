# Viberayd/Viberoxy v1 Feature Recipes (implemented 2026-08-11)

Concrete recipes from the v1 feature round. Each was shipped as a fork PR
with TDD; reproduce the pattern, not the exact code.

## 1. Latency threshold (Viberayd) — PR #6

Goal: `DAEMON_MAX_LATENCY_MS` env; configs that PASS the test but exceed the
threshold are treated as failed (excluded from working.txt).

Recipe:
- `DaemonConfig.MaxLatencyMs int`, default 0 (disabled), clamp `< 0 → 0`
  with warn.
- `ApplyResults(s, results, now, maxLatencyMs ...int)` — **variadic** so the
  4 existing test call sites compile unchanged.
- Inside: `success := r.Success; if success && threshold > 0 && r.LatencyMs >
  threshold { success = false }`.
- On the failure path, still record `r.LatencyMs` when > 0 (visibility in
  state.json) — a test caught the naive version that zeroed it.
- Tests: over-threshold→failed, at-threshold→working, 0→disabled,
  working-config-demoted.

## 2. Mux + socket tuning (Viberoxy) — PR #5

Goal: kill per-connection setup latency.

Recipe:
- `Config.XrayMux bool`, default true, `XRAY_MUX` env via `strconv.ParseBool`
  (hard error on garbage).
- `BuildXrayConfig(cfg, port, muxEnabled ...bool)` — variadic, default true;
  `StartXray` threads it through.
- `buildOutbound(cfg, muxEnabled)` — `mux := &MuxConfig{Enabled:true,
  Concurrency:8}` when on; **nil** on freedom fallbacks (test asserts no mux
  on hysteria2).
- `tuneTCPConn(conn net.Conn)`: `SetNoDelay(true)`, `SetKeepAlive(true)`,
  `SetKeepAlivePeriod(30s)`; call on both ends in `relayThroughWAN` and right
  after `socks5Dial`'s dial.
- Old test `Mux.Enabled == false` flips to `== true` + concurrency check;
  add explicit `BuildXrayConfig(cfg, port, false)` test.

## 3. Split routing (Viberoxy) — PR #6

Goal: geofile-style `ROUTE_MODE` + domain lists.

Recipe:
- New `router.go`: `Route` enum (WAN/Direct), `RouteMode` string consts,
  `ParseRouteMode` (hard error), `Router{Mode, directSuffixes,
  proxySuffixes}`, `Decide(target)`, `normalizeHost` (strip :port + trailing
  dot + lowercase), `matchesAny` (dot-prefix → domain+subdomains, else exact),
  `parseSuffixList` (comma env), `loadSuffixFile` (newline file, `#`
  comments).
- Config: `ROUTE_MODE`, `DIRECT_DOMAINS`, `PROXY_DOMAINS`,
  `DIRECT_LIST_FILE`, `PROXY_LIST_FILE`. Build `Router` only when mode !=
  all-proxy OR lists non-empty → default path untouched.
- Front-ends: decide BEFORE `GetLeastLoaded`. Direct → `directDial` (30s
  timeout, tuned) + `directRelay` (pipe + access log `route=direct`) — both
  in `relay.go`; variadic `router ...*Router` on `NewProxyServer`/
  `NewSocksServer` keeps existing tests compiling.
- Metrics: `viberoxy_proxy_bytes_total` gets `route="direct"` series.
- Integration test trick: direct route must succeed with an **empty WAN
  pool** (WAN path would 503) → proves the router gates the decision.
- README: mode table + examples (`.ir` country-local, geo-blocked list).

## Pending roadmap (v2+)

- **DNS-over-proxy** (viberoxy): SOCKS5 UDP ASSOCIATE + xray inbound
  `udp:true` + UDP relay. Sized as real work, not a one-liner.
- **Protocol gap:** hysteria2/tuic/wireguard have NO real xray outbound →
  currently excluded by `IsXraySupported` (freedom = leak). Need native
  outbounds or accept exclusion.
- **geosite.dat parsing** vs plain-text lists (v1 chose text = zero-dep).
- **F5 bundler + WebUI:** repo `yolka-wiz/viber-console` **created
  (2026-08-12)** with the read-only backend shipped (Prometheus parser,
  poll store, `/api/*`, smoke test — see `references/viber-console-backend.md`).
  Still pending: frontend (deliberately deferred — user wants data-contract
  planning first), install bundle (install.sh, systemd units, compose),
  config editing + auth.
