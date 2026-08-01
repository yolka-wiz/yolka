# Viberoxy Simulation Findings (2026-08-01, first production run)

Context: Viberoxy (Go daemon, HTTPS CONNECT proxy at :10908, least-connections
LB over 3 xray WANs on 10700-10702, sub from viberayd :8084/sub, FETCH_INTERVAL
720min, MINIMUM_SPEED 8 Mbps). Simulated 10 users, max 3 concurrent, 6-page
stateful sessions, 130 tracked requests, 167.7s runtime.

## Exit IP stability — SEVERE churn

Every user bounced across 2-5 unique exit IPs in a 6-page session; 20+ distinct
exit IPs across the run from only 3 WANs.

Per-WAN direct probe (localhost SOCKS port, 3x each):
```
WAN 10700 (138.68.53.88): 144.31.99.228 → 62.60.229.255 → 144.31.126.232
WAN 10701 (138.68.53.88): 95.143.111.212 → 5.181.20.175  → 185.239.142.215
WAN 10702 (173.245.59.1): 51.38.127.93   → 51.38.127.93   → 51.38.127.93
```
Two WANs rotate their own egress IP per connection (upstream behind multi-IP
pool/CDN). Only one WAN is stable. Conclusion: IP churn is STRUCTURAL (upstream
pools), not just LB rotation — sticky LB alone cannot fix it.

## Latency — unusable for interactive browsing

| metric | all reqs | cookie-echo | exit-ip |
|---|---|---|---|
| mean   | 3.64s | 3.43s | 3.79s |
| median | 2.37s | 2.46s | 2.12s |
| p95    | 11.49s| 8.90s | 12.01s |
| max    | 12.02s| 12.01s| 12.02s |

## Hard failures — 5.4% full hangs

7/130 requests hung the full 12s `-m` cap then died (code 000), scattered
across users/pages. Root cause: `GetLeastLoaded()` is purely connection-count
based with NO health exclusion; a dead WAN at 0 connections is the most
attractive pick. No exclusion of failing WANs between 12h cycles.

## Cookie / session persistence — mostly client-side OK, 10% silent loss

- Client-side jars persist fine; proxy does not mangle cookies.
- 6/60 cookie-echo requests returned HTTP 200 but the session cookie was
  missing from the echo → server-side session lost (server sees a "new
  visitor" every request, consistent with IP churn).

## Protocol quirks

- CONNECT-only: plain HTTP absolute-form GET → 405 Method Not Allowed. Only
  HTTPS sites are browsable.
- Duplicate WANs: 2 of 3 active WANs were the SAME upstream (138.68.53.88 x2,
  selected from two different subscription configs). Startup does not dedupe
  by server:port.
- Latent direct-egress leak: xray.go maps hysteria2/tuic/wireguard → `freedom`
  (direct) outbound. If such a config ever passes MINIMUM_SPEED, traffic
  egresses directly from the host's real public IP (46.34.180.79 for
  core-srv), silently bypassing the proxy. Not in pool at test time (all
  vless), but a landmine.

## External vs proxy attribution

- httpbin.org returned 503 even DIRECT — external problem, not the proxy's.
  Through the proxy it also produced full 12s hangs on some WANs → WAN
  quality divergence. Always baseline direct first.

## Recommended follow-ups (not yet done)

- LB health exclusion (skip WANs that failed N consecutive checks)
- Client/WAN stickiness (affinity key) to reduce churn — note it won't fully
  fix upstream-pool churn on the two rotating WANs
- Dedupe WAN selection by server:port
- Guard the freedom-fallback path (drop unsupported protocols or log loudly)
