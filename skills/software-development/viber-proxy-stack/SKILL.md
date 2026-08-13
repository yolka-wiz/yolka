---
name: viber-proxy-stack
description: "Develop on the Viber proxy stack: Viberayd + Viberoxy."
version: 1.0.0
author: yolka
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [viber, viberayd, viberoxy, proxy, xray, go, subscriptions, socks5, wan]
    related_skills: [github-pr-workflow, fork-safe-project-rename, git-essentials]
---

# Viber Proxy Stack

Use when the user asks to improve, extend, or debug **Viberayd**, **Viberoxy**
(two Go proxy projects by `amirrezaalavi`, actively developed via the
`yolka-wiz` forks), or **viber-console** (the control-plane/WebUI project that
bundles and supervises both).

## Topology (who does what)

| Piece | Role | Repos |
|---|---|---|
| **Viberayd** | Subscription **aggregator/prober** daemon: fetches subscription URLs, tests configs (TCP → TLS → protocol → xray), persists state, serves working configs as a subscription endpoint (`/sub`) | upstream `amirrezaalavi/Viberayd` · fork `yolka-wiz/Viberayd` |
| **Viberoxy** | **Proxy server**: aggregates working configs into a pool of persistent xray **WANs**, exposes them behind a health-aware least-connections load balancer via HTTPS CONNECT (`PROXY_PORT`) + SOCKS5 (`SOCKS_PORT`) | upstream `amirrezaalavi/Viberoxy` · fork `yolka-wiz/Viberoxy` |
| **viber-console** | **Bundler + WebUI control plane** (BUILT 2026-08-13): supervises both daemons as child processes, aggregates status (Viberayd JSON API + Viberoxy Prometheus), schema-driven env-file config editor with restart, single-page SPA (dark/light, mobile-first, zero frontend deps) | `yolka-wiz/viber-console` (own repo, NOT a fork — created by user direction) |

Viberayd is the *prober/feed*; Viberoxy is the *egress*. Viberayd answers
"which configs work?" — Viberoxy answers "how do I serve traffic through the
best ones?". viber-console answers "how do I run and control both from one UI?".
See `references/viber-console-architecture.md` for the console's full design,
API contract, and Go-stdlib gotchas.

## Delivery mechanics (established pattern)

- Both `yolka-wiz` forks exist. Work on the fork, PR to `amirrezaalavi/*` main.
- All prior PRs merged via this path (branch per feature, Conventional Commits,
  one feature per PR). Small, reviewable diffs; `go vet ./...` + full tests
  green before opening the PR.
- No secrets: no subscription URLs, API keys, or real credentials in commits.
- Version-drift risk: keep bundled binaries / docs pinned to upstream versions.

## Conventions (both projects)

- **Zero dependencies**: Go stdlib only (Viberoxy's `go.mod` has NO requires;
  Viberayd likewise). Do not add packages casually — it breaks a hard rule.
  xray-core is an *external runtime* dep (in PATH), not a Go dep.
- **Env-var config**, validated at startup. Viberoxy: bad value = hard exit.
  Viberayd: clamp out-of-range with a warning (never fail on `parallel=100`).
- **Logging**: `slog.Info/Warn/Error` with key-value pairs. Never `log.Println`.
- **Error wrapping** (Viberayd): `fmt.Errorf("context: %w", err)`.
- **State files** (Viberayd): atomic tmp+rename only.
- **Concurrency**: channels over mutex in Viberayd; mutex per WAN slot + atomic
  counters in Viberoxy.

## Key files

Viberayd (`cmd/viberayd`, `internal/daemon/{config,state,fetcher,tester,loop,http,signals}.go`,
`internal/tester/`, `internal/concurrency/`, `pkg/parser/`):
- `config.go` — env parsing + clamping; `state.go` — `ApplyResults` (state
  transitions), `SelectCandidates`; `tester.go` — latency from pipeline
  `Latencies.Total` (fallback Response); `loop.go` — working.txt + `/sub`.

Viberoxy (flat package in repo root):
- `main.go` — env parsing, startup, runCycle; `parser.go` — `ParseSingle`
  (8 protocols) + `IsXraySupported`; `xray.go` — `BuildXrayConfig` +
  `buildOutbound`; `tester.go` — `socks5Dial` + `DownloadMeasurer`;
  `wan.go` — slot state machine (`empty→testing→active→draining`);
  `proxy.go` + `socks.go` — front-ends sharing `wanRelay` plumbing.

## Known findings / sharp edges (verified 2026-08-11, updated 2026-08-13)

- **Mux was DISABLED on every xray outbound** → every client connection
  triggered a full upstream protocol handshake = the dominant per-connection
  latency. **FIXED 2026-08-13** (Viberoxy PR #5): `XRAY_MUX` env, default
  `true`, emits `mux {enabled:true, concurrency:8}` on proxied outbounds
  (never on freedom fallback), plus `tuneTCPConn` (TCP_NODELAY + keepalive
  30s) on both relay legs and the socks5Dial. Trade-off: mux slightly caps
  per-stream throughput on huge transfers — `XRAY_MUX=false` restores old
  behavior.
- **`IsXraySupported` excludes hysteria2/tuic/wireguard** because
  `buildOutbound` maps them to a `freedom` outbound = direct egress = traffic
  leak. They parse fine but must never be promoted to a WAN slot. Viberayd
  DOES test these protocols — asymmetry between prober coverage and proxy
  support is an open improvement target.
- **SOCKS5 front-end rejects UDP ASSOCIATE (REP 0x07)** and xray inbound has
  `"udp": false` → DNS-over-proxy is real work (UDP relay + inbound flag),
  not a footnote. Split-routing v1 ships TCP-only; DNS stays client-side and
  is documented as v2 (needs SOCKS5 UDP + xray `udp:true`).
- **Split routing shipped 2026-08-13** (Viberoxy PR #6): `ROUTE_MODE`
  all-proxy|proxy-default|direct-default + `DIRECT_DOMAINS`/`PROXY_DOMAINS`/
  `DIRECT_LIST_FILE`/`PROXY_LIST_FILE`. Router built only when non-default
  mode or any list set. `route=direct|wan` in access log + metrics. Direct
  path dials straight from the box (tuned conns), bypasses WAN pool.
- **Viberayd module path is `github.com/amirrezaalavi/Viberay`** (repo named
  Viberayd) — mechanical rename PR is open (PR #5); branch off main, sed
  `module` line + all imports + `go mod tidy`, verify full suite before PR.

## Roadmap status (plan `.hermes/plans/2026-08-11_viber-stack-features.md`)

| # | Item | Status |
|---|---|---|
| 1 | Viberayd README standalone (docs) | ✅ PR #4 open |
| 1b | Viberayd go.mod rename | ✅ PR #5 open (mechanical; merge-order note below) |
| 2 | Viberayd `DAEMON_MAX_LATENCY_MS` threshold | ✅ PR #6 open |
| 3 | Viberoxy latency fix (mux + NODELAY + AsIs) | ✅ MERGED (PR #5) |
| 4 | Viberoxy split routing (`ROUTE_MODE` + domain lists) | ✅ MERGED (PR #6) |
| 5 | viber-console bundle + WebUI | ✅ BUILT 2026-08-13 (`yolka-wiz/viber-console`); install/bundle layer (systemd, compose) still pending |

**Viberayd merge-order caveat:** #5 (module rename) and #6 (threshold) both
touch `internal/daemon/` — merging #5 first means #6 needs an import-path
rebase. Safest: #4 → #6 → #5. Never merge two overlapping PRs and assume the
conflict resolution is right — see the merge-repair pitfall below.

## Merging overlapping PRs: verify the conflict resolution (lesson 2026-08-13)

When two PRs touch the same files and the maintainer merges them with an
intermediate "Merge branch 'main' into <feature>" commit, **the conflict
resolution can be silently botched** even though GitHub shows MERGED. This
happened on Viberoxy: PRs #5+#6 both added `tuneTCPConn`/`directRelay` to
`relay.go`; the resolution left `relayThroughWAN`'s signature nested inside
`directRelay`'s body (syntax error), broke `main.go`'s brace balance, and
dropped an AGENTS.md entry — `go build` failed on merged main.

Verification + repair procedure (worked, cheap, reusable):

1. **After any overlapping merge, `git fetch origin && git reset --hard
   origin/main && go build ./...`** — a compile failure on merged main is the
   tell. Also `grep -rn '<<<<<<<\|>>>>>>>'` for leftover conflict markers.
2. **Reconstruct the correct union locally** before touching anything: the
   two feature-branch tips are usually still in the object store
   (`git cat-file -t <sha>`), so build a scratch branch off the pre-merge
   base and merge both branches with `git merge --no-edit`, resolving
   conflicts deliberately (take the file version that already contains the
   union, then hand-merge the truly conflicting hunks).
3. **Diff the reconstruction against `origin/main`** (`git diff origin/main
   --stat`) — this enumerates exactly what the botched resolution broke.
4. **Apply a minimal surgical fix PR** (in this case +3/−5 lines over 3
   files): restore the function bodies, close the brace, restore the dropped
   doc line. Verify `go build && go vet && go test ./... && go test -race`
   on the fixed tree, then PR the fix.
5. Identical-added-hunk note: when both branches add the *same* helper
   (e.g. `tuneTCPConn`), git usually auto-merges identical hunks — the
   breakage comes from overlapping-but-different edits. Tell the maintainer
   in the PR body which files/hunks were wrong so the merge can be re-done
   cleanly instead of patched around.

## Working style (user preference, from 2026-08-11)

- **Never front-load a multi-option clarify for an undefined "improve X"
  task.** The user will say "stop, I'll tell you" and dictate direction.
  Ask open-ended or wait.
- User approves scope explicitly before destructive work (deletes, renames,
  mass rewrites). For repo teardown/backup, see `git-workspace-teardown` /
  `project-state-archival`.
- Plans land in `.hermes/plans/` with a self-critique section (SPOFs, missing
  backups, complexity vs value).
