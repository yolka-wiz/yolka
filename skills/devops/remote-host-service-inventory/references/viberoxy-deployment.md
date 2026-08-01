# Viberoxy Deployment on core-srv (192.168.4.120)

Session detail: deploy Viberoxy (github.com/amirrezaalavi/Viberoxy) on a remote Debian host, connected to viberayd's sub feed, running as a systemd service. Includes two upstream code bugs that had to be patched — **re-apply them after pulling fresh upstream; they are NOT in the repo**.

## What Viberoxy is

Zero-dependency Go daemon: fetch subscription → parse (ss/vmess/vless/trojan/hy2/tuic/wg/socks5) → speed-test each config through a temp xray on TEST_BASE_PORT → keep top N as persistent xray WANs on WAN_BASE_PORT+i → expose a single CONNECT-only HTTPS proxy (PROXY_PORT) with least-connections load balancing. All config via env vars (`parseConfig` in main.go).

Env vars: `SUBSCRIBER_URL` (required), `FETCH_INTERVAL` (s, min 30), `TEST_TIMEOUT` (s, min 3), `DOWNLOAD_SIZE` (bytes, min 1e6), `DOWNLOAD_ENDPOINT` (default cloudflare speed), `DOWNLOAD_FALLBACK`, `WAN_COUNT` (1–5, default 4), `WAN_BASE_PORT` (default 10700), `TEST_BASE_PORT` (default 10800), `PROXY_PORT` (default 1080), `MINIMUM_SPEED` (Mbps, min 0.1, default 5.0).

## Deployed config

Systemd unit `/etc/systemd/system/viberoxy.service`:

- `User=core`, `WorkingDirectory=/opt/viberoxy`, `ExecStart=/opt/viberoxy/viberoxy`
- `SUBSCRIBER_URL=http://127.0.0.1:8084/sub` (viberayd's HTTP sub endpoint; ~57 KB, 85–97 configs)
- `FETCH_INTERVAL=43200` (720 min), `WAN_COUNT=3`, `MINIMUM_SPEED=8`, `PROXY_PORT=10908`
- WAN xrays listen on 127.0.0.1:10700–10702; user-facing proxy on 0.0.0.0:10908
- Host prereqs: Go 1.26.5 at /usr/local/go, xray 26.7.11 at /usr/local/bin (copied from viberayd container via `sudo docker cp viberayd:/usr/local/bin/xray /usr/local/bin/xray`)

## Bug 1 — all speed tests fail instantly (xray readiness race)

**Symptom:** log shows `startup: testing configs... count=85` then `not enough configs passed minimum speed` one second later; `active=0`. The whole 85-config loop completes in <1 s — far too fast for real 10 MB downloads.

**Root cause:** `StartXray` (`cmd.Start()`) returns as soon as the process spawns, but xray takes ~100 ms to bind its SOCKS port. Production `TestSpeed` dials immediately → `connection refused` for every config. The repo's own tests know about this (`waitForPort` in tester_test.go, used by `TestTestSpeed`), but it was never wired into production code.

**Fix (tester.go):** after `StartXray`, wait for the port before `DownloadMeasurer`:

```go
if err := waitPortReady(socksAddr, 5*time.Second); err != nil {
    return &TestResult{Config: cfg, Error: fmt.Errorf("xray not ready: %w", err)}
}
```

plus a `waitPortReady(addr string, timeout time.Duration) error` helper (net.DialTimeout loop, 50 ms poll).

**Empirical confirmation:** `xray -c cfg &` then probing `/dev/tcp/127.0.0.1/20899` — port opens after ~100 ms.

## Bug 2 — startup retry wipes already-active WANs

**Symptom:** log shows `wan active index=0`, then `wan active index=1`, then `not enough configs passed minimum speed ... active=0` — both WAN xrays killed on retry. Startup can never reach WAN_COUNT if a single pass through the subscription doesn't find all N passers.

**Root cause (main.go, startup retry path):**

```go
for _, idx := range pool.GetSlotsByState(StateActive, StateTesting) {
    pool.ResetEmpty(idx)   // ResetEmpty kills the xray process
}
```

**Fix:** only reset stuck testing slots, keep active WANs:

```go
for _, idx := range pool.GetSlotsByState(StateTesting) {
    pool.ResetEmpty(idx)
}
```

Note: `runCycle` (steady state) does NOT have this bug — only `startup`.

## Verification after deploy

- `journalctl -u viberoxy` should show `wan active index=0/1/2` then `viberoxy started wans=3 proxy_port=10908`.
- `ss -tln` shows 127.0.0.1:10700–10702 + `*:10908`.
- Egress check from another host (exit IP must differ from direct — proves tunneling):
  ```bash
  curl -s -x http://192.168.4.120:10908 https://api.ipify.org
  curl -s https://api.ipify.org   # control
  ```
- Startup takes minutes: each candidate costs a 10 MB download test; first pass through ~85 configs can take up to ~14 min (stops early once 3 passers found). Watch with a poll loop, not a single check.

## Pitfalls

- **Local Go too old** (`go1.24.4` vs `go 1.26.5` in go.mod) → `go build` tries GOTOOLCHAIN download from proxy.golang.org → 403 on restricted networks. Build on the target which has the right toolchain.
- **go.dev/dl lists a version but the download 404s** — `go.dev/dl/go1.26.5.linux-amd64.tar.gz` 302s to `dl.google.com` which 404s from multiple network paths. Use `https://mirrors.aliyun.com/golang/go1.26.5.linux-amd64.tar.gz`, verify sha256 from `https://go.dev/dl/?mode=json`.
- **tar to /usr/local needs sudo** — plain `tar -C /usr/local -xzf` fails as non-root with a wall of "Cannot mkdir: Permission denied"; use `sudo tar`.
- **The upstream repo still contains both bugs** — they are local patches only. Re-apply after any fresh pull/upgrade of Viberoxy.
