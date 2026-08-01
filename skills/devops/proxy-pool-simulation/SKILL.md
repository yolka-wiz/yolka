---
name: proxy-pool-simulation
description: Simulate users through a proxy pool to find quirks.
category: devops
version: 1.0.0
---

# Proxy Pool Simulation

Validate an egress proxy / WAN aggregation pool (Viberoxy, viberayd, any HTTPS CONNECT or SOCKS5 load-balanced pool) under concurrent multi-user **stateful** browsing before real users hit it. The goal is finding quirks: session stickiness, exit-IP churn, latency distribution, hard timeouts, cookie loss.

## When to Use

- User asks to "simulate a company of N users" or "stress-test the proxy" / "find quirks / session problems"
- Before rolling out a proxy pool to real users
- After changing WAN_COUNT, LB policy, or subscription source
- Any time a proxy is expected to preserve stateful sessions (banking, SSO, streaming, geo-bound apps)

## Method

1. **Probe single-request behavior first** (before building the harness):
   - HTTPS via CONNECT: `curl -x http://host:port https://api.ipify.org`
   - Plain HTTP absolute-form: expect `405` on CONNECT-only proxies (document it as a quirk)
   - Exit IP across 5 sequential CONNECTs → count unique IPs (quick churn signal)
2. **Baseline the target site DIRECT (no proxy)** — a `503` may be the site's problem, not the proxy's. Never blame the proxy without the direct baseline.
3. **Per-WAN diagnostic (the key step)**: hit each WAN's local SOCKS port directly 3×:
   `curl --socks5-hostname 127.0.0.1:<wanport> https://api.ipify.org`
   This separates **LB-level rotation** (pool picks a different WAN per connection) from **per-WAN upstream churn** (the upstream itself exits via a multi-IP pool/CDN). If a single WAN rotates its own egress IP per connection, no LB stickiness can fix it — that's structural.
4. **Run the harness** (`scripts/proxy_pool_sim.py`): N users, M concurrent (BoundedSemaphore), P pages/user, per-user cookie jars, per-request exit-IP + latency + cookie-echo tracking. Writes results/errors/ips JSON to /tmp for post-analysis.
5. **Analyze**: unique IPs per user vs flips, latency percentiles (median/p95/max), timeout count (`000`), cookie-echo loss on HTTP 200.

## Quirks to Look For (findings from a real Viberoxy run — see references/viberoxy-simulation-findings.md)

| Quirk | Signal | Root cause |
|---|---|---|
| Exit IP rotates per request | every user sees 2–5 unique IPs per 6-page session; 20+ IPs from 3 WANs | least-connections LB + upstreams behind multi-IP pools/CDNs |
| Full-timeout hangs | requests hit exact `-m` cap then `000` (5–10%) | LB picks dead WANs: 0 connections = most attractive to least-connections, no health exclusion |
| Silent cookie loss | HTTP 200 but session cookie missing from echo | server sees a "new visitor" every request due to IP churn |
| CONNECT-only | `405` on plain HTTP GET | proxy only implements CONNECT |
| Duplicate WANs | 2 of 3 WANs same upstream host | startup doesn't dedupe by server:port |
| Direct-egress leak (latent) | exit IP == host's real public IP | config builder maps unsupported protocols (hysteria2/tuic/wireguard) to a `freedom`/direct outbound |

## Pitfalls

- Use `curl -m` matching real-client expectations and count `000` (timeout) separately from HTTP codes — they hide in latency stats otherwise.
- Track exit IP via `https://api.ipify.org` (lightweight, rarely blocks). For cookie echo use `postman-echo.com` (`/cookies/set?k=v` then `/cookies`) — httpbin.org 503s even direct, don't trust it as a target.
- Per-user cookie jars must be separate temp files; each simulated user is a thread with its own jar to test cross-request state.
- Keep think-time jitter (0.4–1.6s) or the harness becomes a pure concurrency hammer and misses stateful-session behavior.
- The harness shells out to `curl` per request — it's stdlib-only and runs anywhere; no pip deps.
- When reporting: always include the direct-vs-proxy baseline and the per-WAN diagnostic — that's what separates "proxy is broken" from "upstream pool churns".

## Files

- `scripts/proxy_pool_sim.py` — runnable harness (env-configurable users/pages/concurrency/proxy/targets)
- `references/viberoxy-simulation-findings.md` — full findings from the first production run
