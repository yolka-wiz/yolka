---
name: dev-toolchain-provisioning
description: "Provision Rust/Go/Python toolchains user-locally + mirrors."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [dev-toolchain, rust, go, python, uv, mirrors, aliyun, provisioning]
    related_skills: [agent-workspace-provisioning, mirror-discovery, remote-server-operations]
---

# Dev Toolchain Provisioning

Use when the user asks to install or set up language toolchains (Rust, Go, Python) on a Linux box,
or to route package managers through a mirror (e.g. `mirrors.aliyun.com`). Prefers **user-local
installs over system override** and real end-to-end verification over version output.

## Core principles

- **User-local first, never system override**: rustup → `~/.cargo` + `~/.rustup`, Go tarball →
  `~/.local/go`, uv → `~/.local/bin`, Python venv under the workspace. On Debian 13+ system python
  is externally-managed (PEP 668) — never pip into it. No sudo, no apt toolchain packages.
- **Verify with real fetches, not just versions**: `cargo build` a scratch crate, `go get` a real
  module, `uv pip install` a package. Versions alone don't prove the mirrors work.
- **Wire PATH once, serially, in `~/.bashrc`** (or a dedicated block at the end). Never let parallel
  subagents append to the same dotfile — appends race.
- **Check network BEFORE installing**: probe endpoints with GET, not HEAD (see pitfalls), and use
  deep paths (`/dists/<codename>/Release`, `/simple/<pkg>/`) rather than roots.

## Steps

1. **Inventory**: `command -v` for each tool, OS/arch (`cat /etc/os-release`, `uname -m`), disk, sudo.
2. **Network probe**: for each needed endpoint run `curl -s -o /dev/null -w '%{http_code}' -m 8 <GET url>`.
   Confirm direct egress vs proxy; check env vars and any known LAN SOCKS fallback.
3. **Install per toolchain** (non-interactive, no sudo):
   - **Rust**: download `rustup-init` binary, then run
     `./rustup-init -y --profile minimal --default-toolchain stable --no-modify-path`,
     then `rustup component add rustfmt clippy`. (Download-then-run beats `curl | sh` — the pipe
     gives no progress and can hang an agent's iteration budget.)
   - **Go**: `curl -s https://go.dev/dl/?mode=json | python3 -c ...` to get latest stable version,
     filename and sha256 (filter out beta/rc); download tarball; `echo '<sha>  file' | sha256sum -c -`;
     `tar -C ~/.local -xzf` (after `rm -rf ~/.local/go`); `go env -w GOPROXY=...`.
   - **Python**: install uv (standalone installer or pip-in-throwaway-venv fallback);
     `uv venv <workspace>/agent-env --python 3.x`; `uv pip install ruff mypy pytest build`.
4. **Apply the mirror to EVERY surface**: apt sources (backup first), `~/.config/pip/pip.conf`,
   `~/.config/uv/uv.toml`, `~/.cargo/config.toml` (sparse registry), `go env -w GOPROXY`,
   `RUSTUP_DIST_SERVER`/`RUSTUP_UPDATE_ROOT` exports. For Aliyun specifics see
   `references/aliyun-mirror-layout.md`.
5. **Wire `~/.bashrc`** (single serial append): PATH for `~/.cargo/bin` and `~/.local/go/bin`,
   plus rustup mirror env vars. Go's GOPROXY/GOSUMDB persist via `go env -w` (writes
   `~/.config/go/env`) — no bashrc needed for those.
6. **Verify each mirror with a real fetch**, then write/update AGENTS.md with versions, mirror
   config, and caveats.

## Pitfalls

- **Subagents are unreliable for critical installs**: delegated installs can die on infra
  (session-storage write failure, iteration-budget exhaustion) and may self-report "completed"
  without success. Do installs directly; treat any subagent success as a claim to verify yourself
  (`rustc --version`, `go version`, `uv --version`).
- **Some packages don't expose `__version__`** (e.g. `rich`): a failed `import rich; rich.__version__`
  can look like a broken install. Verify via module path (`inspect.getfile`) or `pip show <pkg>`
  instead of version attributes.
- **HEAD probes lie on API endpoints**: crates.io API, go.dev/dl JSON, and PyPI index pages return
  403/405 to `curl -I` but work fine with GET. Always probe with GET.
- **dl.google.com can 404 Go tarballs even when go.dev JSON advertises them** (publishing/CDN
  glitches). Fetch the identical tarball from a mirror (e.g. `mirrors.aliyun.com/golang/`) and
  verify its sha256 against the JSON — the checksum is the ground truth.
- **Go sumdb through a proxy**: with GOPROXY set, sumdb lookups go THROUGH the proxy
  (`/sumdb/sum.golang.org/...`); mirrors like Aliyun 404 those tiles. Fix with
  `go env -w GOSUMDB=off` — existing `go.sum` files still verify pinned hashes; only public sumdb
  consultation is lost.
- **Mirror gaps are normal**: mirrors often miss small bootstrap artifacts (e.g. Aliyun lacks the
  `rustup-init` installer). Probe the mirror layout first, fetch missing bits from upstream, and
  route the heavy components through the mirror.
- **Don't conclude a mirror is dead from one root-path probe**: use deep paths (dists/Release,
  `/simple/<pkg>/`, module `@v/list`). Root URLs often 404/redirect while deep paths serve fine.

## Reference

- `references/aliyun-mirror-layout.md` — verified Aliyun surface matrix, config snippets, and
  end-to-end verification proofs.
