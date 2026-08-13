# Xray Config Facts (verified against Viberoxy/Viberayd work, 2026-08)

Condensed xray-core config knowledge for the proxy-stack daemons. Source:
working `xray.go` / `BuildXrayConfig` implementations and upstream behavior.

## Outbounds

### Proxied protocols (ss / vmess / vless / trojan / socks)
- The target domain is passed to the remote server **untouched** — no local
  DNS resolution on this path. `domainStrategy` in outbound settings does
  NOT apply here; don't add it.
- `mux: {"enabled": true, "concurrency": 8}` multiplexes many client
  connections over ONE upstream connection. This is the dominant lever on
  per-connection setup latency (amortizes TLS/protocol handshake).
- Mux trade-off: slight per-stream throughput ceiling on very large single
  transfers → keep an env opt-out (e.g. `XRAY_MUX=false`).
- vless user map: `{"id", "encryption"}` (+ `flow` when present).
- vmess user map: `{"id", "alterId", "security": "auto"}`; `net`/`type`/
  `path`/`host`/`tls`/`sni`/`fp`/`alpn` come from the sharelink JSON.

### freedom (direct) outbound
- `domainStrategy` DOES apply: `UseIP` / `UseIPv4` / `UseIPv6` / `AsIs`.
- **Leak hazard:** mapping hysteria2/tuic/wireguard to `freedom` = direct
  egress = traffic leak. Guard with an `IsXraySupported()`-style check so
  such configs are never promoted to a WAN slot.

### streamSettings per network
- `ws`: `wsSettings.path` + `wsSettings.headers.Host`
- `grpc`/`gun`: `grpcSettings.serviceName` (from `path`)
- `tcp` + http header: `tcpSettings.header = {type:"http", request:{version,
  method:"GET", path:["/"], headers:{Host:[host]}}}`
- `tls`: `tlsSettings.serverName` (from `sni`), `fingerprint`, `alpn` (split
  on comma)
- `reality`: `realitySettings.serverName` (sni), `fingerprint`, `publicKey`,
  `shortId`, `spiderX` — note: current builder only sets serverName +
  fingerprint; reality publicKey/shortId must come from sharelink params.

## Inbounds (socks)
- `{"protocol":"socks", "listen":"127.0.0.1", "port":N,
  "settings":{"udp":false}}` — `udp:false` means **no DNS-over-proxy** via
  this inbound; enabling DNS-over-proxy requires `udp:true` + a UDP-capable
  front-end relay.
- xray binds the SOCKS port asynchronously after spawn → always
  `waitPortReady` before dialing (classic "connection refused every test").

## Runtime facts
- Spawn via `exec.Command("xray", "-c", tmpConfig)`; config written to a
  temp file, removed on stop. Stop = SIGTERM → wait → SIGKILL.
- `HealthCheckXray(cmd)` = process-alive check only (not a port probe).
- Mux concurrency: 8 is a sane default; 0/omitted means xray default.
