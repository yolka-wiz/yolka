# viber-console — architecture & Go stdlib gotchas (built 2026-08-13)

Control plane for the viber stack: `yolka-wiz/viber-console` (own repo, NOT a
fork; created by user direction — the only viber repo not on the fork→PR
pattern). Console supervises both daemons as children, aggregates status, and
edits their env-file config from a single-page WebUI.

## Constraints that shaped the design (user brief)

- Must **install/bundle/run both projects** (owns their lifecycle)
- Must **control both** — change core params, not just read status
- Simple but **modern** look; **one main page**; **mobile-friendly**
- Server **< 150 MB RAM**; **few dependencies** (family rule: Go stdlib only)

## Stack decisions

- Go stdlib backend (existing dashboard API) + **embedded vanilla JS/CSS SPA**
  via `//go:embed` — zero frontend deps, no npm/build/CDN, offline.
  Estimated RSS 20–35 MB, far under the 150 MB ceiling.
- **Light/dark theme toggle** (user decision): default follows
  `prefers-color-scheme`, manual toggle in `localStorage`; CSS variables for
  both palettes. Dark + light palettes defined on `[data-theme=...]`.
- **Supervisor model** (user decision): console spawns viberayd+viberoxy as
  child processes (Docker-friendly, restart from UI trivially). systemd is
  OPTIONAL, only for the console itself.
- Config surface = the daemons' **env files** (`/etc/viber/{viberayd,viberoxy}.env`)
  — their only config mechanism. Schema-driven editor, atomic write + `.bak`
  rollback, restart after save.

## Package layout

```
cmd/console/            # env parsing, wiring, supervisor boot
internal/collector/     # HTTP client, stdlib Prometheus text parser, viberayd/viberoxy clients
internal/config/        # editable env-var schema (38 fields), atomic env-file store, validation
internal/dashboard/     # poll store + /api handlers + control API + embedded SPA
internal/supervisor/    # child-process manager (start/restart/stop, stderr ring tail)
internal/dashboard/static/  # index.html + styles.css + app.js (go:embed all:static)
docs/                   # data-contract.md + frontend-design.md
scripts/                # smoke.sh (backend), ui-smoke.sh / ui-stack.sh (WebUI)
```

## API contract (backend, read + control)

Read (shipped first, read-only phase):
- `GET /api/health`, `GET /api/overview` (one-call snapshot),
  `GET /api/viberayd/configs?page=&per_page=&state=`, `GET /api/viberayd/urls`,
  `GET /api/viberoxy/metrics`

Control (added 2026-08-13, the "controller not dashboard" phase):
- `GET /api/config/schema` — editable fields per group, drives the form
- `GET/POST /api/config/values` — read / atomic-write env files (+ optional
  restart); validation client-side AND server-side
- `GET /api/processes` — pid, uptime, restarts, last error, stderr tail
- `POST /api/control/restart` — service `viberayd|viberoxy|all`
- Auth: `CONSOLE_TOKEN` bearer; empty token = localhost-only. Checked on all
  `/api/*` except `/api/health`. Localhost default is the security posture.

Design docs live in the repo: `docs/data-contract.md` (what data flows),
`docs/frontend-design.md` (SPA + control design, decisions recorded).

## Go stdlib gotchas (each cost a debug cycle — know these)

1. **`go:embed` cannot use `..` in patterns.** `//go:embed all:../../static`
   → `invalid pattern syntax`. Static files must live INSIDE the package dir
   (we moved `static/` → `internal/dashboard/static/`). HTTP URLs stay
   `/static/*` regardless of disk location.
2. **`http.FileServer` redirects `/` to `./` (301)** — it treats `/` as a
   directory. Serve `index.html` bytes explicitly for `/` (read once via
   `fs.ReadFile(sub, "index.html")`, write with `Content-Type: text/html`),
   and let FileServer handle only `/static/*`. Don't fight the redirect.
3. **`exec.Cmd.Wait()` must be called from exactly ONE goroutine.** Calling
   it from both the reaper goroutine and `Stop()` deadlocks (second Wait
   blocks). Pattern: reaper owns `cmd.Wait()` and `close(s.exitCh)`; `Stop()`
   signals SIGINT then `select { <-exitCh, <-time.After(5s) → SIGKILL }`.
4. **Shell children ignore SIGINT forked to a script.** `sh -c 'sleep 30'`
   doesn't die on the parent's SIGINT — the 5s SIGKILL fallback in Stop is
   essential, and tests must assert restart-count/lifecycle, not fast exit.
5. **stdout vs stderr in supervisor tests**: `echo` writes stdout; the
   supervisor tails **stderr only** — tests must `echo x >&2`.
6. **Prometheus text parsing stdlib-only**: needed because Viberoxy has NO
   JSON API. Parser handles `name{labels} value`, `_bucket`/`_sum`/`_count`
   histogram lines, drops `+Inf` bucket, estimates percentiles by linear
   interpolation within buckets. Percentiles computed backend-side so the
   frontend stays dumb.
7. **Poll-store pattern for dashboards**: backend polls daemons on an
   interval into a mutex-guarded snapshot; handlers serve the snapshot, so a
   dead daemon yields `"reachable": false` instead of hanging/erroring the UI.
8. **Env-file store**: write `file.tmp` (0600), keep old file as `.bak`,
   rename over. Missing env file at boot = start with inherited env (daemon
   defaults apply), don't fail startup.
9. **`go:embed` + SPA shell**: keep section anchors (`id=`) stable — smoke
   test greps for them to prove the shell rendered.

## Verification recipe (all real, 2026-08-13)

- `go build ./... && go vet ./... && go test ./... && go test -race ./...`
- `node --check internal/dashboard/static/app.js` (JS syntax; node is
  available, no browser is — DOM-level render checks not possible here)
- `scripts/ui-smoke.sh`: boots mock viberayd (python http.server :18081) +
  mock viberoxy (:19090, Prometheus text) + real console binary, curls the
  SPA shell, CSS/JS, schema API, POSTs a config change, asserts the env file
  was written. This is the end-to-end proof; keep it runnable.
- Simulating the JS data flow with `node -e` + `fetch` against the live stack
  proves every endpoint the frontend consumes returns the shape app.js expects.

## Frontend design (for the future UI work)

One page, four sections under a sticky header: stat cards → WAN slot cards →
configs table (cards on mobile) → settings form (schema-driven, tabs per
daemon, Save & Restart). Mobile: single column, 44px touch targets, table→
card-list below 700px. Theme toggle in header. All icons inline SVG, system
font stack, `Intl.NumberFormat` for numbers — zero external assets.
