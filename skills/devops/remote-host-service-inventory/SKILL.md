---
name: remote-host-service-inventory
description: Enumerate services on remote Linux hosts over SSH.
category: devops
version: 1.0.0
---

# Remote Host Service Inventory

Read-only reconnaissance of a known remote Linux server: what services run, what listens, what containers/clusters/VM workloads exist, and what's broken. Use when the user asks "what services are on X", "what's running on that machine", or before any mutation on a host you haven't inspected this session.

## When to Use

- "What services are on machine X?" / "what's running on core-srv?"
- Pre-change baseline before touching a server (always inventory before mutate)
- Verifying a server's health after an incident or reboot
- Finding which SSH user/port works on an unfamiliar host

## Core Principle

**Read-only first, always.** Inventory commands must not mutate anything. Batch independent probes in parallel (systemd, ports, docker, k3s, incus, disk) — they're independent reads.

## Workflow

### 1. Find the working SSH user (if unknown)

Don't guess one account at a time — batch-test candidates in a single loop:

```bash
for u in core root admin alavi agent; do
  echo "== $u =="
  timeout 6 ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=4 $u@HOST 'hostname' 2>&1 | head -2
done
```

The user that echoes back the right hostname is your access. Check `~/.ssh/config` first — host aliases and ProxyJump entries reveal the intended path (e.g. an Incus container at a different IP reachable only via a jump).

### 2. Parallel service survey (the four-layer sweep)

Run these in parallel (independent reads):

```bash
# systemd + uptime
ssh -o BatchMode=yes core@HOST 'uptime; systemctl list-units --type=service --state=running --no-pager --no-legend | awk "{print \$1}"; systemctl list-unit-files --type=service --state=enabled --no-pager --no-legend | awk "{print \$1}"'

# listening ports (sudo needed for process names; fall back to plain ss)
ssh -o BatchMode=yes core@HOST 'sudo ss -tlnp 2>/dev/null || ss -tlnp 2>/dev/null'

# containers / cluster / VMs
ssh -o BatchMode=yes core@HOST 'sudo docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"'
ssh -o BatchMode=yes core@HOST 'sudo k3s kubectl get nodes -o wide; sudo k3s kubectl get pods -A; sudo k3s kubectl get svc -A'
ssh -o BatchMode=yes core@HOST 'incus list'
```

Ready-to-run copy: [scripts/service_inventory.sh](scripts/service_inventory.sh) — run `./service_inventory.sh user@host`.

### 3. Identify mystery ports and containers

- Ports owned by `docker-proxy` → map back to `docker ps -a` ports column.
- Unknown image name → `sudo docker inspect <name> --format ...` for Image/Cmd/Mounts/Env, and `sudo docker logs <name> | tail -15` to learn what it actually does (e.g. a "viberayd" container turned out to be a v2ray subscription validator probing ~5k candidates per cycle).
- `curl -s -m 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:PORT/` on each listener to see if it actually serves.

### 4. Cross-check against expected state

If notes/memory claim services on specific ports (mirror server, dashboard), probe those ports explicitly and **report downed services as discrepancies** — don't silently present the new state as if nothing changed. A service in the notes but not listening is a finding, not a footnote.

### 5. Deliver

Present a compact table: service / port / status. Flag broken services with a ⚠️. **When the user asked for an inventory, deliver the inventory** — offer to fix what's broken, but don't fix without being asked (user's preference: "Nothing, just wanted the inventory").

## Pitfalls

- **`docker.sock: permission denied`** — the SSH user isn't in the docker group. This is NOT Docker being down — retry with `sudo docker ps`. (On core-srv: `core` user needs sudo for docker; k3s/incus don't.)
- **`journalctl` says "No entries"** — the SSH user isn't in `adm`/`systemd-journal` groups, so it can't read the journal. Don't conclude the service never logged. Instead, run the binary directly with a timeout to see the live fatal error:
  ```bash
  sudo timeout 2 /usr/local/bin/<svc> run --config /etc/<svc>/config.toml 2>&1 | head -5
  ```
- **`bind: cannot assign requested address` in a crash-looping service** — the service's config pins an IP the host doesn't own (or owns on the wrong interface). Diagnose by comparing `ip -4 addr show` against the config listener IP. Real case: ctrld bound `192.168.4.109:53` but the host's .109 was on `br13` (192.168.13.109/24), not on ens192 (192.168.4.120/24) — the config had the wrong subnet. Also note `systemctl status` shows `activating (auto-restart)` + `Result: exit-code` for this.
- **Enabled ≠ running**: `systemctl list-unit-files --state=enabled` includes services that crash-loop on boot. Always compare enabled vs running lists.
- **Single-node k3s**: check `svc -A` for the LoadBalancer's EXTERNAL-IP — it maps host ports (e.g. Traefik `80:30314/TCP,443:30102/TCP`).
- **Incus bridge IPs** (e.g. 192.168.13.109 on br13) look like they belong to another subnet — they're the host-side bridge legs. Don't confuse them with LAN NICs.

## Verification

- Every claimed listener has a matching `curl` probe or is explained by a container/k3s mapping.
- Every downed service from step 4 is explicitly reported.
- No command in this skill mutates the target — read-only confirmed by construction.

## Deploying a Compiled Go Daemon on the Target (post-inventory)

After inventory, deploying a Go daemon to run on the host (systemd, no container) — e.g. Viberoxy proxy-pool aggregator. Full worked example with two upstream code bugs fixed: [references/viberoxy-deployment.md](references/viberoxy-deployment.md).

### Toolchain version mismatch → build on the target, not locally

- `go.mod` can require a newer Go than the local box (`go 1.26.5` vs local `go1.24.4`). With a mismatch, local `go build` triggers GOTOOLCHAIN auto-download from `proxy.golang.org`, which can 403 on restricted networks. **Fix:** install the exact toolchain version on the target and build there — scp the source (tar excluding `.git`), run `go build` remotely, run the binary on that same host.
- Install Go from the official JSON index: `https://go.dev/dl/?mode=json` (returns versions + sha256). **Pitfall:** the file URL `go.dev/dl/go1.26.5.linux-amd64.tar.gz` may 302 to `dl.google.com` and 404 there even though the index lists it (edge/CDN propagation, seen from multiple network paths). **Fix:** pull the same file from a mirror such as `https://mirrors.aliyun.com/golang/go1.26.5.linux-amd64.tar.gz`, verify against the sha256 from the JSON, extract with `sudo tar -C /usr/local -xzf` (non-root can't write to `/usr/local`).

### Reuse binaries already on the box instead of downloading

- If a Docker container already ships a needed binary (e.g. xray inside a `viberayd` container), don't download it — extract it: `sudo docker cp <container>:/usr/local/bin/xray /usr/local/bin/xray` + `chmod 755`. Version matches the container's toolchain exactly.

### systemd unit for env-var-configured services

- Put every env var as an `Environment=` line in the unit (no shell sourcing), set `WorkingDirectory=` to the source dir (daemons write debug files there), `Restart=on-failure`, `RestartSec=15`, `LimitNOFILE=65536`. Write the unit with `write_file` locally and `scp` it — never inline heredocs.

### Verify long-running startup, not just "active"

- A service can show `active (running)` while its startup loop silently fails (e.g. every speed test errors instantly). Don't trust the unit state: read `journalctl -u <svc>` for cycle/progress lines, confirm the daemon reached its "started" log line, and check expected listening ports before calling it done. Startup that does real network probing can take minutes — poll with a loop rather than a single check.

### Keep verification evidence until the user confirms

When a verification harness (or the user) asks for proof that code changes work, create a rerunnable temp script + focused test, run it, and **keep the artifacts** (`/tmp/hermes-verify-*.sh`, `/tmp/hermes-verify-*.log`, and the temp `_test.go` dropped into the package) until the work is accepted. Deleting them makes the run look unverified and forces a do-over. Pattern that worked:

- Temp `_test.go` in the package exercising the **patched code path** (real subprocess spawn, not a mock) — e.g. `TestHermesVerifyTestSpeedThroughPatch` and `TestHermesVerifyStartupRetryKeepsActiveWANs`.
- Script flow: bundle source (tar excluding `.git`) → scp → extract → `go build` → `go vet ./...` → full `go test ./...` → focused `go test -run TestHermesVerify -v` → live service state (`systemctl is-active`, listener count, "started" log line) → functional egress check.
- `exec > >(tee "$LOG")` so the log persists as evidence; remove the temp test from the deployed tree afterward (it's scaffolding, not product code), but keep script + log.
- If the harness still reports "unverified" after cleanup, re-run the script and leave the artifacts in place.

## GitHub collaboration setup (SSH key + MCP) for repo work

When the user wants you to push changes and use GitHub tooling, see [references/github-collaboration-setup.md](references/github-collaboration-setup.md) — covers the dedicated SSH key + `~/.ssh/config` host block, `hermes mcp add github` registration (interactive prompt needs `echo Y |`), PAT scope requirements, and the pull-only-token symptom (MCP reads work, create/merge PRs fail).
