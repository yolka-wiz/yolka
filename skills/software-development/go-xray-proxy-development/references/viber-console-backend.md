# viber-console Backend Patterns (implemented 2026-08-12)

The control-plane backend that aggregates Viberayd + Viberoxy into one JSON
API. Repo: `yolka-wiz/viber-console` (own repo, NOT a fork — created directly
on the user's GitHub).

> **Status update (2026-08-13):** the read-only phase documented below is
> DONE and the project moved on — the console now also **supervises both
> daemons as child processes**, edits their env files via a schema-driven
> config API (`/api/config/schema`, `/api/config/values`,
> `/api/processes`, `/api/control/restart`), and ships a **single-page SPA**
> (dark/light theme, mobile-first, zero frontend deps, embedded via
> `//go:embed`). See the comprehensive architecture reference in the
> `viber-proxy-stack` skill: `references/viber-console-architecture.md`
> (Go-stdlib gotchas: go:embed `..` rule, FileServer `/` redirect,
> exec.Cmd.Wait single-goroutine rule, supervisor SIGINT fallback).

## Key facts that shaped the design

- **Viberayd has a JSON API** (`/api/stats`, `/api/configs?page=&per_page=`,
  `/api/urls`, `/api/health`, `/metrics`) — easy to poll.
- **Viberoxy has NO JSON API** — only Prometheus text `/metrics` +
  `/healthz` + `/readyz`. The console must parse Prometheus text itself.
  Decision: the console owns aggregation; daemons stay zero-dep.
- Metric names to read from viberoxy: `viberoxy_wans_active`,
  `viberoxy_wan_speed_mbps{index}`, `viberoxy_wan_stability{index}`,
  `viberoxy_proxy_connections_total{wan,proto}`,
  `viberoxy_proxy_bytes_total{wan,direction}`,
  `viberoxy_proxy_latency_seconds` (histogram),
  `viberoxy_test_duration_seconds` (histogram),
  `viberoxy_build_info{version}`.

## Stdlib Prometheus text parser (the reusable piece)

`internal/collector/prometheus.go` — zero-dep parser for the subset emitted
by the viber stack:

- Bare lines `name{labels} value`; strip `# HELP`/`# TYPE` comments.
- Histogram family: `name_bucket{le="X"}` lines grouped by family, `+Inf`
  bucket dropped, `name_sum`/`name_count` captured. Buckets are cumulative.
- Labels: `a="1",b="2"` — split on commas respecting quoted commas.
- `Percentile(buckets, p)` — linear interpolation within the cumulative
  bucket that crosses the target count. Standard approach; verify with a
  small unit test (p50/p95/p100 on a toy bucket set).
- `FindGauge(samples, labels)` — value lookup with label-subset matching.

## Poll-store design (graceful degradation)

- Backend polls daemons on an interval (default 10s) into an in-memory
  snapshot cache (mutex). Handlers serve snapshots — the frontend never
  calls daemons directly.
- A dead/slow daemon → `"reachable": false` in the JSON, NOT an HTTP error.
  Test this path explicitly (unreachable viberoxy URL → overview still 200
  with `reachable:false`).
- `GET /api/overview` is the one-call dashboard snapshot: viberayd stats +
  viberoxy WAN slots (per-slot speed/stability/conns + per-protocol
  breakdown) + proxy counters + latency p50/p95/p99 + healthz/readyz.

## Mock-daemon smoke test pattern

`scripts/smoke.sh` — boots two tiny `python3 http.server` mocks (viberayd
JSON on :18081, viberoxy Prometheus on :19090), builds and runs the real
binary, curls the endpoints, asserts shapes. This proves end-to-end
behavior without needing the real daemons (or xray, or a subscription).
Write it so a future session can run `bash scripts/smoke.sh` and see the
aggregated JSON.

## Env config (mirrors family style)

`CONSOLE_LISTEN` (:8090), `CONSOLE_POLL_INTERVAL` (10s),
`VIBERAYD_API_URL` (http://127.0.0.1:8081), `VIBERAYD_SUB_URL`
(http://127.0.0.1:8080), `VIBEROXY_METRICS_URL` (http://127.0.0.1:9090),
`CONSOLE_LOG_LEVEL` (info|debug).

## Open questions — RESOLVED (2026-08-13)

- Auth for config editing → **`CONSOLE_TOKEN`** bearer token; empty =
  localhost-only. Checked on all `/api/*` except `/api/health`.
- Should console edit daemon env files / restart units? → **yes, console owns
  it**: schema-driven env-file store (atomic tmp+rename + `.bak`) +
  supervisor restart. Daemons are console-managed children, not systemd.
- Persist timeseries history? → **v1 = snapshots only**; no history yet.
