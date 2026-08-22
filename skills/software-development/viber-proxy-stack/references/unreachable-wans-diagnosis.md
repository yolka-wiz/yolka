# "WANs show as unreachable" — diagnosis recipe (2026-08-15)

User report on a live viber-console (e.g. `http://192.168.4.120:8090/`): "the
WebUI shows viberoxy is working, but in the WANs section all the WANs show as
unreachable." The WANs were actually healthy. This is the workflow that found
the real cause, in the order that avoids wasted frontend work.

## Step 1 — Pull the live API data before touching the frontend

```bash
curl -s http://<host>:8090/api/overview | python3 -m json.tool
```

The overview carries per-slot `speed_mbps` / `stability` / `conns`. If slots
exist with non-zero speeds, **the WAN section is fine** — viberoxy metrics are
reaching the console and parsing correctly. In the actual incident:
`wans.active: 3`, slots at 11.6 / 18.9 / 22.7 Mb/s, `reachable: true`. The
problem was NOT in the WAN data path.

## Step 2 — Rule out a stale frontend: diff deployed assets against the repo

The console embeds its SPA via `go:embed`; a binary built from an older commit
would serve older JS/CSS. Diff the deployed static files byte-for-byte:

```bash
curl -s http://<host>:8090/static/app.js   -o /tmp/live-app.js
curl -s http://<host>:8090/                -o /tmp/live-index.html
diff /tmp/live-app.js     <repo>/internal/dashboard/static/app.js
diff /tmp/live-index.html <repo>/internal/dashboard/static/index.html
```

Identical = the running frontend is current. Do NOT start "fixing the UI".

## Step 3 — Read the renderer: what CAN it display?

`renderWANs` in `app.js` renders speed/stability/connections only — there is
**no "unreachable" string in the WAN section at all**. So "unreachable" pills
the user sees must come from the **Configs section** (viberayd's per-config
table): `<span class="pill err">unreachable</span>` via `stateClass()`. The
sections sit adjacent on the single page — WANs section above, configs below —
so a user describing "WANs section" is very likely looking at the config table.

## Step 4 — Confirm the data source

```bash
curl -s "http://<host>:8090/api/viberayd/configs?page=1&per_page=100" | python3 -c \
  "import json,sys; from collections import Counter; d=json.load(sys.stdin); \
   print(Counter(x['state'] for x in d['configs']))"
```

Actual: `{unreachable: 99, failed: 1}` in the first 100, and stats showed
`unreachable: 10000` out of `total: 10117`. Mass "unreachable" is the tell.

## Root cause — viberayd's TCP-ping pre-filter, not the console

`internal/daemon/tester.go` `TCPPing` does a **direct TCP connect** to every
candidate host (200-way parallel, short timeout) *before* any xray test. Hosts
that don't answer a bare TCP connect → state `unreachable`, skipped, never get
an xray test.

On networks that filter/DPI direct egress to foreign IPs (e.g. Iran), direct
TCP connects to random foreign IPs/ports get dropped while the same hosts work
fine **through xray** (protocol-encrypted, e.g. vmess/vless/trojan). That is
exactly why viberoxy's WANs work (they connect via proxy protocols) while
viberayd marks ~99% of configs unreachable (they die on direct egress).

Corroborating evidence: the *working* WANs had `latency_p50_s ≈ 0.5`,
`p95 ≈ 1.9` — very high, consistent with a degraded/limited direct path where
only the most reachable hosts sneak through.

Ranked suspects:
1. Network blocks direct TCP to foreign IPs (DPI/filtering) — fits all evidence.
2. `DAEMON_TIMEOUT` too low for the ping stage — can amplify #1.
3. Host-level egress restriction on the box running viberayd.

## Fix candidates (upstream, not console)

- Raise `DAEMON_TIMEOUT` via the WebUI settings → Apply, see if unreachable
  drops.
- Real fix: make the TCP-ping stage **non-fatal / skippable** — on filtered
  networks the ping pre-filter is a blunt instrument; either skip ping for
  configs that fail direct connect and let the xray test be the judge, or make
  the stage configurable. This is a Viberayd change, not a console change.

## Fix SHIPPED 2026-08-15 — `DAEMON_TCP_PING` toggle (Viberayd PR #8)

User chose "go with the fix" → implemented as an opt-in toggle (default
preserves current behavior):

- New env **`DAEMON_TCP_PING`** (default `true` = current fast prefilter).
- `false`: **skip the TCP prefilter entirely** — every candidate goes to the
  xray test, which is the authoritative judge. No `unreachable`-marking from
  the ping stage at all, so previously pre-killed configs get a real chance
  and the pool recovers.
- Implemented in `internal/daemon/loop.go` `runCycle`: when enabled, run
  `TCPPing` + mark/skip failures (old path); when disabled, build survivors
  from ALL candidates + `slog.Info("tcp ping disabled, testing all candidates
  via xray", "count", ...)`.
- Config: `DaemonConfig.TCPPing bool` + env parse (`true`/`1`/`yes`),
  documented in README env table, default-true asserted in
  `TestDefaultConfig`, plus `TestLoadConfigTCPPingOff`/`On`.
- Console: `DAEMON_TCP_PING` added to viber-console settings schema
  (`internal/config/schema.go`, bool, default `true`) so it is a WebUI toggle
  on the Viberayd settings tab → Save & Restart.
- **Trade-off (say it plainly in the PR):** disabling the ping means every
  candidate costs an xray test — slower cycles on huge subscriptions. That is
  the price of correctness on filtered networks; leave it on where direct TCP
  works.
- Deployment note: flipping the toggle in the WebUI restarts the daemon; the
  next cycle xray-tests the full candidate set and previously-unreachable-but-
  alive hosts get promoted.

## Reusable general lesson

- **UI symptom → check the API/data first.** The console already aggregates
  the daemons; `curl /api/overview` shows whether the *data* is wrong before
  assuming the *renderer* is wrong.
- **Diff deployed static assets against the repo** to rule out a stale embedded
  build — cheap and definitive for `go:embed` SPAs.
- **Read the renderer to enumerate what it CANNOT display** — if the section
  has no code path for the reported label, the label is coming from another
  section or another layer.
- **Mass state labels from a probe pre-filter ≠ component failure.** Trace the
  state machine: viberayd `unreachable` means "direct TCP ping failed", which
  is a *network property*, not a daemon/console bug.
